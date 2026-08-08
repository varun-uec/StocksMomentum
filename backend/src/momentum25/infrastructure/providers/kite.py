"""Zerodha Kite Connect v3 market-data adapter (Phase 5.2) — licensed feed.

Replaces spoofed-User-Agent scraping with Zerodha's official, licensed API. The
endpoints, headers, parameters and response shapes below were taken from the
published Kite Connect v3 documentation (``kite.trade/docs/connect/v3``,
retrieved 2026-08-08), not assumed:

* ``GET /instruments/:exchange`` — CSV dump, columns
  ``instrument_token, exchange_token, tradingsymbol, name, last_price, expiry,
  strike, tick_size, lot_size, instrument_type, segment, exchange``.
  **It carries no ISIN** — see :meth:`KiteConnectProvider.fetch_instrument_master`.
* ``GET /instruments/historical/:instrument_token/:interval`` with ``from``/``to``
  as ``yyyy-mm-dd hh:mm:ss`` — returns ``{"data": {"candles": [[ts, o, h, l, c, v], ...]}}``.
* Auth: header ``Authorization: token api_key:access_token`` and ``X-Kite-Version: 3``.
* Session: ``POST /session/token`` with ``api_key``, ``request_token`` and
  ``checksum = sha256(api_key + request_token + api_secret)``.
* Rate limits: historical candles 3 req/s, quotes 1 req/s, everything else 10 req/s.
* ``access_token`` expires at 6 AM the next day (regulatory); a 403 /
  ``TokenException`` means a fresh interactive login is required. There is no
  refresh flow for standard accounts.

Layering: :class:`KiteHttpClient` is the entire HTTP surface (one protocol, one
httpx implementation, no logic). Everything with behaviour — instrument mapping,
rate limiting, candle parsing, error classification — lives in
:class:`KiteConnectProvider` and the pure helpers, and is unit-tested against a
fake client. Nothing here has been exercised against a live Kite account: this
platform holds no Kite credentials.
"""

from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import time
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

import httpx

from momentum25.domain.ports.market_data import RawBar, RawInstrument
from momentum25.infrastructure.logging.setup import get_logger

_logger = get_logger("kite")

KITE_API_ROOT = "https://api.kite.trade"
KITE_LOGIN_ROOT = "https://kite.zerodha.com/connect/login"

# Documented rate limits (Kite Connect v3, "API rate limit").
_HISTORICAL_REQUESTS_PER_SECOND = 3.0
_DEFAULT_REQUESTS_PER_SECOND = 10.0


class KiteError(RuntimeError):
    """A Kite Connect API error, carrying the API's own ``error_type``."""

    def __init__(self, message: str, error_type: str = "GeneralException", status: int = 0) -> None:
        """Store the API-reported message, exception name and HTTP status."""
        super().__init__(message)
        self.error_type = error_type
        self.status = status


class KiteTokenExpiredError(KiteError):
    """The access token expired or was invalidated (HTTP 403 / ``TokenException``).

    Kite access tokens die at 6 AM daily by regulation; recovery requires the
    interactive login flow, so this is raised as its own type rather than being
    retried (a retry can only ever fail again).
    """


def kite_login_url(api_key: str) -> str:
    """Return the interactive login URL that yields a ``request_token`` (pure)."""
    return f"{KITE_LOGIN_ROOT}?v=3&api_key={api_key}"


def session_checksum(api_key: str, request_token: str, api_secret: str) -> str:
    """Return ``sha256(api_key + request_token + api_secret)`` (pure)."""
    return hashlib.sha256(f"{api_key}{request_token}{api_secret}".encode()).hexdigest()


async def exchange_request_token(
    api_key: str,
    api_secret: str,
    request_token: str,
    client: httpx.AsyncClient | None = None,
    root: str = KITE_API_ROOT,
) -> str:
    """Exchange a one-time ``request_token`` for a daily ``access_token``.

    Step 3 of the documented login flow: the operator opens
    :func:`kite_login_url`, logs in, and the registered redirect URL receives a
    ``request_token`` valid for a few minutes. This POSTs it with the checksum
    to ``/session/token``. There is no way to automate the interactive step —
    Zerodha requires a human login every day.
    """
    payload = {
        "api_key": api_key,
        "request_token": request_token,
        "checksum": session_checksum(api_key, request_token, api_secret),
    }
    headers = {"X-Kite-Version": "3"}
    url = f"{root.rstrip('/')}/session/token"
    if client is not None:
        response = await client.post(url, data=payload, headers=headers)
    else:
        async with httpx.AsyncClient(headers=headers, timeout=30) as owned:
            response = await owned.post(url, data=payload)
    if response.status_code >= 400:
        raise _error_from_response(response.status_code, _safe_json(response))
    access_token = ((response.json() or {}).get("data") or {}).get("access_token")
    if not access_token:
        raise KiteError("Kite session response carried no access_token")
    return str(access_token)


def _to_decimal(value: Any) -> Decimal:
    """Convert a JSON number to ``Decimal`` via its string form (no float drift)."""
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def parse_candles(payload: Any, symbol: str) -> list[RawBar]:
    """Parse a Kite historical-candles response body into ``RawBar`` rows (pure).

    Each candle is ``[timestamp, open, high, low, close, volume]`` with an
    ISO-8601 timestamp such as ``"2017-12-15T09:15:00+0530"``; an ``oi=1``
    request appends a seventh element, which is ignored. Malformed candles are
    skipped and logged rather than defaulted to a fabricated value.
    """
    candles = ((payload or {}).get("data") or {}).get("candles") or []
    bars: list[RawBar] = []
    for candle in candles:
        if not isinstance(candle, list) or len(candle) < 6:
            _logger.warning("kite_candle_skipped_malformed", symbol=symbol)
            continue
        try:
            bar_date = datetime.fromisoformat(str(candle[0])).date()
            bars.append(
                RawBar(
                    symbol=symbol,
                    date=bar_date,
                    open=_to_decimal(candle[1]),
                    high=_to_decimal(candle[2]),
                    low=_to_decimal(candle[3]),
                    close=_to_decimal(candle[4]),
                    volume=int(candle[5] or 0),
                )
            )
        except (ValueError, TypeError) as exc:
            _logger.warning("kite_candle_skipped", symbol=symbol, error=str(exc))
    bars.sort(key=lambda b: b.date)
    return bars


def parse_instruments_csv(text: str, exchange: str) -> list[RawInstrument]:
    """Parse the Kite instruments CSV into equity ``RawInstrument`` rows (pure).

    Keeps only ``instrument_type == "EQ"`` rows for ``exchange``. ``isin`` and
    ``listing_date`` stay ``None``: the CSV has neither column.
    """
    reader = csv.DictReader(io.StringIO(text))
    instruments: list[RawInstrument] = []
    for row in reader:
        cell = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
        if cell.get("instrument_type") != "EQ" or cell.get("exchange") != exchange:
            continue
        symbol = cell.get("tradingsymbol", "").upper()
        if not symbol:
            continue
        instruments.append(
            RawInstrument(
                symbol=symbol,
                name=cell.get("name") or symbol,
                series=cell.get("instrument_type"),
            )
        )
    return instruments


def parse_instrument_tokens(text: str, exchange: str) -> dict[str, int]:
    """Return ``tradingsymbol -> instrument_token`` for equities on ``exchange`` (pure).

    Kite's own guidance: key on ``(exchange, tradingsymbol)``, never on the
    numeric token alone, because tokens are recycled across derivative expiries.
    """
    reader = csv.DictReader(io.StringIO(text))
    tokens: dict[str, int] = {}
    for row in reader:
        cell = {(k or "").strip(): (v or "").strip() for k, v in row.items()}
        if cell.get("instrument_type") != "EQ" or cell.get("exchange") != exchange:
            continue
        symbol = cell.get("tradingsymbol", "").upper()
        try:
            token = int(cell.get("instrument_token", ""))
        except ValueError:
            continue
        if symbol:
            tokens[symbol] = token
    return tokens


class KiteHttpClient(Protocol):
    """The complete HTTP surface of the Kite adapter (no logic lives here)."""

    async def get_json(self, path: str, params: dict[str, str] | None = None) -> Any:
        """GET ``path`` and return the decoded JSON body."""
        ...

    async def get_text(self, path: str) -> str:
        """GET ``path`` and return the raw response body as text."""
        ...


class HttpxKiteClient:
    """``httpx`` implementation of :class:`KiteHttpClient`.

    Thin by design: it adds the two documented headers, performs the request and
    translates HTTP/API errors into :class:`KiteError`. It contains no mapping,
    caching, retry or rate-limiting behaviour, so it is correct by inspection —
    which matters because it cannot be integration-tested without live
    credentials.
    """

    def __init__(
        self,
        api_key: str,
        access_token: str,
        client: httpx.AsyncClient | None = None,
        root: str = KITE_API_ROOT,
    ) -> None:
        """Bind the client to a Kite app key and a (daily) access token."""
        self._root = root.rstrip("/")
        self._headers = {
            "X-Kite-Version": "3",
            "Authorization": f"token {api_key}:{access_token}",
        }
        self._client = client

    async def get_json(self, path: str, params: dict[str, str] | None = None) -> Any:
        """GET ``path`` and return the decoded JSON body."""
        response = await self._request(path, params)
        return response.json()

    async def get_text(self, path: str) -> str:
        """GET ``path`` and return the raw response body as text."""
        response = await self._request(path, None)
        return response.text

    async def _request(self, path: str, params: dict[str, str] | None) -> httpx.Response:
        """Perform the GET and raise :class:`KiteError` on any non-2xx response."""
        url = f"{self._root}{path}"
        if self._client is not None:
            response = await self._client.get(url, params=params, headers=self._headers)
        else:
            async with httpx.AsyncClient(headers=self._headers, timeout=30) as client:
                response = await client.get(url, params=params)
        if response.status_code >= 400:
            raise _error_from_response(response.status_code, _safe_json(response))
        return response


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    """Return the decoded error body, or an empty mapping if it is not JSON."""
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _error_from_response(status: int, body: dict[str, Any]) -> KiteError:
    """Map a Kite error body to the matching exception type (pure)."""
    error_type = str(body.get("error_type") or "GeneralException")
    message = str(body.get("message") or f"Kite request failed with HTTP {status}")
    if status == 403 or error_type == "TokenException":
        return KiteTokenExpiredError(message, error_type=error_type, status=status)
    return KiteError(message, error_type=error_type, status=status)


class _RateLimiter:
    """Serializes calls to a minimum interval (deterministic, no jitter)."""

    def __init__(self, requests_per_second: float) -> None:
        """Configure the minimum interval between dispatches."""
        self._min_interval = 1.0 / requests_per_second
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def acquire(self) -> None:
        """Wait until the next dispatch is permitted."""
        async with self._lock:
            elapsed = time.monotonic() - self._last
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last = time.monotonic()


class KiteConnectProvider:
    """Market-data adapter over Kite Connect v3.

    Implements the data-fetching half of :class:`MarketDataProvider`
    (``fetch_instrument_master``) plus per-symbol daily candles. Three port
    methods are intentionally absent — see :meth:`fetch_eod`,
    :meth:`fetch_benchmark` and :meth:`fetch_corporate_actions` — because Kite
    publishes no equivalent endpoint and a fabricated empty result would be
    worse than an explicit gap.
    """

    def __init__(self, client: KiteHttpClient, exchange: str = "NSE") -> None:
        """Bind the provider to an HTTP client and the exchange to read."""
        self._client = client
        self._exchange = exchange
        self._historical_limiter = _RateLimiter(_HISTORICAL_REQUESTS_PER_SECOND)
        self._default_limiter = _RateLimiter(_DEFAULT_REQUESTS_PER_SECOND)
        self._tokens: dict[str, int] | None = None

    async def fetch_instrument_master(self) -> list[RawInstrument]:
        """Return the current equity instrument master for the bound exchange.

        ``isin`` is always ``None``: the Kite instruments CSV does not publish
        one. Cross-listing reconciliation (Phase 5.1) and every ISIN-keyed
        historical resolution therefore still require an ISIN-carrying source
        (NSE/BSE bhavcopy); Kite cannot replace those paths.
        """
        text = await self._get_instruments_csv()
        return parse_instruments_csv(text, self._exchange)

    async def fetch_historical_bars(
        self, symbol: str, start_date: date, end_date: date | None = None
    ) -> list[RawBar]:
        """Fetch daily candles for one symbol over ``[start_date, end_date]``.

        Returns an empty list for an unknown symbol (logged, never guessed).
        Raises :class:`KiteTokenExpiredError` unchanged so the caller can trigger a
        fresh login rather than treat an expired session as "no data".
        """
        end = end_date or date.today()
        token = await self._instrument_token(symbol)
        if token is None:
            _logger.warning("kite_unknown_symbol", symbol=symbol, exchange=self._exchange)
            return []
        await self._historical_limiter.acquire()
        payload = await self._client.get_json(
            f"/instruments/historical/{token}/day",
            {"from": f"{start_date:%Y-%m-%d} 00:00:00", "to": f"{end:%Y-%m-%d} 23:59:59"},
        )
        return parse_candles(payload, symbol.strip().upper())

    async def fetch_eod_for_symbols(self, symbols: list[str], for_date: date) -> list[RawBar]:
        """Fetch one session's bars for an explicit symbol list.

        Kite has no bulk bhavcopy endpoint, so a session is assembled from one
        rate-limited historical call per symbol (3 req/s). The symbol list is
        required rather than defaulted to the full master: at ~2,000 listed
        equities that would be a ~11-minute, 2,000-call job on every run.
        """
        bars: list[RawBar] = []
        for symbol in symbols:
            bars.extend(await self.fetch_historical_bars(symbol, for_date, for_date))
        return bars

    async def fetch_eod(self, for_date: date) -> list[RawBar]:
        """Not implemented — Kite publishes no whole-market EOD endpoint."""
        raise NotImplementedError(
            "Kite Connect has no bulk EOD/bhavcopy endpoint; use "
            "fetch_eod_for_symbols(symbols, for_date) with the screening universe."
        )

    async def fetch_benchmark(self, index_code: str, for_date: date) -> None:
        """Not implemented — index candles need an index instrument_token mapping."""
        raise NotImplementedError(
            "Kite index history requires an index instrument_token mapping that "
            "has not been verified against a live account; use the NSE provider."
        )

    async def fetch_corporate_actions(self, symbol: str, since: date) -> list[Any]:
        """Not implemented — Kite Connect publishes no corporate-actions endpoint."""
        raise NotImplementedError(
            "Kite Connect publishes no corporate-actions endpoint; returning an "
            "empty list would be indistinguishable from 'no actions'."
        )

    async def _instrument_token(self, symbol: str) -> int | None:
        """Return the instrument token for ``symbol``, loading the map on first use."""
        if self._tokens is None:
            csv_text = await self._get_instruments_csv()
            self._tokens = parse_instrument_tokens(csv_text, self._exchange)
            _logger.info(
                "kite_instrument_tokens_loaded",
                exchange=self._exchange,
                count=len(self._tokens),
            )
        return self._tokens.get(symbol.strip().upper())

    async def _get_instruments_csv(self) -> str:
        """Fetch the instruments CSV dump for the bound exchange."""
        await self._default_limiter.acquire()
        return await self._client.get_text(f"/instruments/{self._exchange}")
