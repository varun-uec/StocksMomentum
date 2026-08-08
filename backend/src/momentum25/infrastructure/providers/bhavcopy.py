"""NSE Bhavcopy market-data provider (MVP primary adapter, ADR-003).

Implements the :class:`MarketDataProvider` port against the official NSE EOD
Bhavcopy archive, via the ``nsemine`` scraping library (synchronous, run in a
worker thread per call). Handles holiday-aware error handling; persistence is
delegated to :class:`SqlOHLCVRepository`.
"""

from __future__ import annotations

import asyncio
import csv
import io
import re
import zipfile
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
import pandas as pd
from nsemine import archives, historical, nse
from tenacity import retry, stop_after_attempt, wait_exponential

from momentum25.domain.ports.market_data import (
    RawBar,
    RawCorporateAction,
    RawIndexBar,
    RawInstrument,
)
from momentum25.infrastructure.logging.setup import get_logger

_logger = get_logger("bhavcopy")

# ── Legacy-archive date routing (RP-012 D1) ───────────────────────────────
# The current provider (NSE ``sec_bhavdata_full``, via nsemine) has data only
# from 2019-09-30 onward — measured precisely (RP-012 D4): the file first
# appears on 2019-09-30 and every prior trading day returns 404. EOD requests
# for dates strictly before that boundary are therefore served from NSE's
# legacy daily-bhavcopy archive, which reaches back to 1994-11-03 (NSE
# equities inception) and remains distinct until the UDiFF cutover (~2024-07).
# The routing rule is a pure, fixed function of ``for_date`` — no config flag,
# no external state — preserving the determinism contract.
_CURRENT_PROVIDER_START: date = date(2019, 9, 30)

_MONTH_ABBR: tuple[str, ...] = (
    "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
    "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
)

# Exact legacy CSV schema (RP-012 §1.2/§2.2). The 2019+ variant appends
# ``TOTALTRADES,ISIN``; parsing by header name tolerates both. Only these
# columns are consumed.
_LEGACY_REQUIRED_COLUMNS: frozenset[str] = frozenset(
    {"SYMBOL", "SERIES", "OPEN", "HIGH", "LOW", "CLOSE", "PREVCLOSE",
     "TOTTRDQTY", "TOTTRDVAL"}
)


def _legacy_archive_url(for_date: date) -> str:
    """Return the legacy NSE bhavcopy archive URL for ``for_date`` (pure)."""
    mon = _MONTH_ABBR[for_date.month - 1]
    return (
        "https://archives.nseindia.com/content/historical/EQUITIES/"
        f"{for_date.year}/{mon}/cm{for_date.day:02d}{mon}{for_date.year}bhav.csv.zip"
    )


def _decimal_or_none(value: str | None) -> Decimal | None:
    """Parse a Decimal from a legacy CSV cell, or ``None`` if blank/invalid."""
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _parse_legacy_bhavcopy(content: bytes, for_date: date) -> list[RawBar]:
    """Parse a legacy bhavcopy ZIP payload into EQ-series ``RawBar`` rows (pure).

    Columns are read by header name against the documented legacy schema
    ``SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,
    TIMESTAMP``. Only ``SERIES == 'EQ'`` rows are kept. ``PREVCLOSE`` and
    ``TOTTRDVAL`` are preserved verbatim (RP-012 §1.2 corporate-action
    inference / §2.2 liquidity gate) — including a genuine reported zero;
    only blank/unparseable cells become ``None`` (never a fabricated value).
    """
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        _logger.warning("legacy_bhavcopy_bad_zip", date=for_date.isoformat())
        return []

    names = archive.namelist()
    if not names:
        return []
    text = archive.read(names[0]).decode("latin1")
    reader = csv.DictReader(io.StringIO(text))
    header = {h.strip().upper() for h in (reader.fieldnames or [])}
    if not _LEGACY_REQUIRED_COLUMNS.issubset(header):
        _logger.warning(
            "legacy_bhavcopy_unexpected_columns",
            date=for_date.isoformat(),
            columns=sorted(header),
        )
        return []

    bars: list[RawBar] = []
    for row in reader:
        cell = {(k or "").strip().upper(): (v or "") for k, v in row.items()}
        if cell.get("SERIES", "").strip().upper() != "EQ":
            continue
        symbol = cell.get("SYMBOL", "").strip().upper()
        if not symbol:
            continue
        # ISIN is present only in the 2019+ legacy schema variant; absent (→ None)
        # for older files. It is the period-correct identity used downstream to
        # resolve the bar to a security robustly to later ticker renames.
        isin = cell.get("ISIN", "").strip().upper() or None
        try:
            bars.append(
                RawBar(
                    symbol=symbol,
                    date=for_date,
                    open=_decimal_or_none(cell.get("OPEN")) or Decimal("0"),
                    high=_decimal_or_none(cell.get("HIGH")) or Decimal("0"),
                    low=_decimal_or_none(cell.get("LOW")) or Decimal("0"),
                    close=_decimal_or_none(cell.get("CLOSE")) or Decimal("0"),
                    volume=int(_decimal_or_none(cell.get("TOTTRDQTY")) or Decimal("0")),
                    prev_close=_decimal_or_none(cell.get("PREVCLOSE")),
                    turnover_value=_decimal_or_none(cell.get("TOTTRDVAL")),
                    isin=isin,
                )
            )
        except (ValueError, TypeError) as exc:
            _logger.warning(
                "legacy_bhavcopy_row_skipped",
                date=for_date.isoformat(),
                symbol=symbol,
                error=str(exc),
            )
    return bars

# nsemine's index history endpoint expects the space-separated NSE index name,
# not the compact code used elsewhere in this codebase (e.g. settings.benchmark_index).
_INDEX_CODE_ALIASES: dict[str, str] = {
    "NIFTY500": "NIFTY 500",
    "NIFTY50": "NIFTY 50",
}

# NSE's corporate-actions endpoint has no dependency-library wrapper (nsemine
# does not expose it) and returns a free-text "subject" field, not a
# structured ratio. Only these two clearly-delimited patterns are parsed into
# a price-adjustment ratio; every other action type (dividends, buybacks,
# rights, AGMs, anything with unrecognized phrasing) is recorded with
# ratio=None and deliberately never adjusts price history -- a wrong guessed
# ratio would silently corrupt every earlier bar, which is worse than a
# disclosed gap (see RawCorporateAction docstring).
_BONUS_RE = re.compile(r"bonus\s+(\d+)\s*:\s*(\d+)", re.IGNORECASE)
_SPLIT_RE = re.compile(
    r"face\s+value\s+split.*?from\s+rs\.?\s*(\d+(?:\.\d+)?).*?to\s+rs\.?\s*(\d+(?:\.\d+)?)",
    re.IGNORECASE,
)

_NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}


def _parse_corporate_action_ratio(subject: str) -> tuple[str, Decimal | None]:
    """Parse a price-adjustment ratio from NSE's free-text corporate-action subject.

    Returns ``(action_type, ratio)``. ``ratio`` is the multiplier to apply to
    prices *before* the ex-date (``adjusted = raw * ratio``); ``None`` if the
    subject doesn't match either recognized pattern.
    """
    bonus_match = _BONUS_RE.search(subject)
    if bonus_match:
        new_shares, held_shares = int(bonus_match.group(1)), int(bonus_match.group(2))
        total = new_shares + held_shares
        if total > 0:
            return "bonus", Decimal(held_shares) / Decimal(total)
        return "bonus", None

    split_match = _SPLIT_RE.search(subject)
    if split_match:
        old_face_value = Decimal(split_match.group(1))
        new_face_value = Decimal(split_match.group(2))
        if old_face_value > 0:
            return "split", new_face_value / old_face_value
        return "split", None

    return "other", None


class BhavcopyProvider:
    """Implements :class:`MarketDataProvider` against the NSE EOD Bhavcopy archive."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        """Bind the provider to an HTTP client.

        Args:
            client: Unused; retained for backward-compatible construction
                (``BhavcopyProvider(httpx.AsyncClient())``). All network access
                is performed by ``nsemine``, which manages its own HTTP session.
        """
        self._client = client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def fetch_eod(self, for_date: date) -> list[RawBar]:
        """Fetch and parse EOD bars for ``for_date``.

        Routes by date (RP-012 D1): requests before ``_CURRENT_PROVIDER_START``
        are served from the legacy NSE archive; on/after it, from the current
        ``sec_bhavdata_full`` provider via nsemine. On weekends/holidays nsemine
        silently returns the most recent prior trading session instead of an
        empty frame, so rows are filtered to ``for_date`` explicitly; a holiday
        therefore yields an empty list rather than misdated data.
        """
        if for_date < _CURRENT_PROVIDER_START:
            return await self._fetch_eod_legacy(for_date)
        try:
            df = await asyncio.to_thread(
                archives.get_daily_bhavcopy_and_deliverables_data,
                series="EQ",
                trade_date=for_date,
            )
        except Exception as exc:
            _logger.warning(
                "bhavcopy_fetch_failed",
                date=for_date.isoformat(),
                error=str(exc),
            )
            return []

        bars: list[RawBar] = []
        if df is None or df.empty:
            return bars

        df = df[df["date"] == for_date]
        if df.empty:
            _logger.warning("bhavcopy_missing_holiday_skipped", date=for_date.isoformat())
            return bars

        for _, row in df.iterrows():
            try:
                symbol = str(row.get("symbol", "")).strip().upper()
                if not symbol:
                    continue
                bars.append(
                    RawBar(
                        symbol=symbol,
                        date=for_date,
                        open=self._to_decimal(row.get("open")),
                        high=self._to_decimal(row.get("high")),
                        low=self._to_decimal(row.get("low")),
                        close=self._to_decimal(row.get("close")),
                        volume=int(row.get("volume", 0) or 0),
                    )
                )
            except (KeyError, ValueError, TypeError) as exc:
                _logger.warning(
                    "bhavcopy_row_skipped",
                    date=for_date.isoformat(),
                    symbol=row.get("symbol"),
                    error=str(exc),
                )
        return bars

    async def fetch_eod_full(self, for_date: date) -> list[RawBar]:
        """Fetch current-provider EOD bars for ``for_date`` with turnover/prev_close.

        Identical routing and holiday handling to :meth:`fetch_eod`, but retains
        the two fields :meth:`fetch_eod` drops — ``previous_close`` and
        ``turnover`` (mapped to ``prev_close``/``turnover_value``). RP-012 Phase 2
        current-provider gap backfill needs the turnover column so the liquidity
        floor is computable for the backfilled securities exactly as it is for the
        rest of ``ohlcv_daily``. Pre-cutover dates still route to the legacy
        archive (which already carries both fields).
        """
        if for_date < _CURRENT_PROVIDER_START:
            return await self._fetch_eod_legacy(for_date)
        try:
            df = await asyncio.to_thread(
                archives.get_daily_bhavcopy_and_deliverables_data,
                series="EQ",
                trade_date=for_date,
            )
        except Exception as exc:
            _logger.warning(
                "bhavcopy_full_fetch_failed", date=for_date.isoformat(), error=str(exc)
            )
            return []

        bars: list[RawBar] = []
        if df is None or df.empty:
            return bars
        df = df[df["date"] == for_date]
        if df.empty:
            _logger.warning("bhavcopy_full_missing_holiday_skipped", date=for_date.isoformat())
            return bars

        for _, row in df.iterrows():
            try:
                symbol = str(row.get("symbol", "")).strip().upper()
                if not symbol:
                    continue
                bars.append(
                    RawBar(
                        symbol=symbol,
                        date=for_date,
                        open=self._to_decimal(row.get("open")),
                        high=self._to_decimal(row.get("high")),
                        low=self._to_decimal(row.get("low")),
                        close=self._to_decimal(row.get("close")),
                        volume=int(row.get("volume", 0) or 0),
                        prev_close=self._num_or_none(row.get("previous_close")),
                        turnover_value=self._num_or_none(row.get("turnover")),
                    )
                )
            except (KeyError, ValueError, TypeError) as exc:
                _logger.warning(
                    "bhavcopy_full_row_skipped",
                    date=for_date.isoformat(),
                    symbol=row.get("symbol"),
                    error=str(exc),
                )
        return bars

    async def fetch_eod_from_legacy_archive(self, for_date: date) -> list[RawBar]:
        """Fetch EOD bars for ``for_date`` explicitly from the legacy NSE archive.

        The routine :meth:`fetch_eod` routes by date and would serve the current
        provider for dates on/after ``_CURRENT_PROVIDER_START``. RP-012 Phase 2
        reconciliation needs the *legacy* source for the overlap window
        (2019-09-30 → ~2024-07-05) regardless of that routing, so this explicit
        entry point bypasses the cutover. It performs no adjustment and returns
        the raw archive prints (``prev_close``/``turnover_value`` populated).
        """
        return await self._fetch_eod_legacy(for_date)

    async def _fetch_eod_legacy(self, for_date: date) -> list[RawBar]:
        """Fetch and parse EOD bars for ``for_date`` from the legacy NSE archive.

        A non-trading day (or any date the archive does not carry) returns 404,
        which is treated as an empty session rather than an error — mirroring
        the holiday handling of the current path. Parsing is delegated to the
        pure :func:`_parse_legacy_bhavcopy` helper.
        """
        url = _legacy_archive_url(for_date)
        try:
            async with httpx.AsyncClient(
                headers={**_NSE_HEADERS, "Referer": "https://www.nseindia.com/"},
                timeout=30,
                follow_redirects=True,
            ) as client:
                resp = await client.get(url)
        except Exception as exc:
            _logger.warning(
                "legacy_bhavcopy_fetch_failed", date=for_date.isoformat(), error=str(exc)
            )
            return []

        if resp.status_code == 404:
            _logger.info("legacy_bhavcopy_missing_nontrading_day", date=for_date.isoformat())
            return []
        if resp.status_code != 200:
            _logger.warning(
                "legacy_bhavcopy_http_error",
                date=for_date.isoformat(),
                status=resp.status_code,
            )
            return []
        return _parse_legacy_bhavcopy(resp.content, for_date)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def fetch_instrument_master(self) -> list[RawInstrument]:
        """Fetch the current NSE equity instrument master list."""
        instruments: list[RawInstrument] = []
        try:
            df = await asyncio.to_thread(nse.get_all_equities_list)
        except Exception as exc:
            _logger.error("bhavcopy_instrument_master_failed", error=str(exc))
            return instruments

        if df is None or df.empty:
            return instruments

        for _, row in df.iterrows():
            try:
                symbol = str(row.get("symbol", "")).strip().upper()
                if not symbol:
                    continue
                instruments.append(
                    RawInstrument(
                        symbol=symbol,
                        name=str(row.get("name", "")).strip() or symbol,
                        isin=str(row.get("isin_number", "")).strip() or None,
                        series=str(row.get("series", "")).strip() or None,
                        listing_date=self._to_date(row.get("date_of_listing")),
                    )
                )
            except (ValueError, TypeError) as exc:
                _logger.warning("bhavcopy_instrument_row_skipped", error=str(exc))
        return instruments

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def fetch_benchmark(self, index_code: str, for_date: date) -> RawIndexBar | None:
        """Fetch the benchmark index close for ``for_date``, if available."""
        nse_index_name = _INDEX_CODE_ALIASES.get(index_code, index_code)
        as_of = datetime.combine(for_date, datetime.min.time())
        try:
            df = await asyncio.to_thread(
                historical.get_index_historical_data,
                index=nse_index_name,
                start_datetime=as_of,
                end_datetime=as_of,
                interval="D",
            )
        except Exception as exc:
            _logger.warning(
                "bhavcopy_benchmark_fetch_failed",
                index=index_code,
                date=for_date.isoformat(),
                error=str(exc),
            )
            return None

        if df is None or df.empty:
            return None

        df = df[df["datetime"].apply(self._to_date) == for_date]
        if df.empty:
            return None

        row = df.iloc[-1]
        try:
            return RawIndexBar(
                index_code=index_code,
                date=for_date,
                close=self._to_decimal(row.get("close")),
            )
        except (ValueError, TypeError) as exc:
            _logger.warning("bhavcopy_benchmark_row_skipped", index=index_code, error=str(exc))
            return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def fetch_corporate_actions(
        self, symbol: str, since: date
    ) -> list[RawCorporateAction]:
        """Fetch corporate actions for ``symbol`` with ``ex_date >= since``.

        Uses NSE's public corporate-actions endpoint directly (no wrapper
        exists in ``nsemine`` for this data). The endpoint returns a free-text
        ``subject`` per action; only "Bonus X:Y" and "Face Value Split ...
        From Rs A To Rs B" are parsed into a price-adjustment ratio (see
        ``_parse_corporate_action_ratio``). Every other action (dividends,
        buybacks, rights, AGMs, unrecognized phrasing) is still returned, with
        ``ratio=None``, so it is visible for audit but never adjusts price
        history.
        """
        try:
            async with httpx.AsyncClient(
                headers=_NSE_HEADERS, timeout=30, follow_redirects=True
            ) as client:
                await client.get("https://www.nseindia.com")
                resp = await client.get(
                    "https://www.nseindia.com/api/corporates-corporateActions",
                    params={"index": "equities", "symbol": symbol},
                )
                resp.raise_for_status()
                rows = resp.json()
        except Exception as exc:
            _logger.warning(
                "bhavcopy_corporate_actions_fetch_failed", symbol=symbol, error=str(exc)
            )
            return []

        actions: list[RawCorporateAction] = []
        for row in rows or []:
            try:
                ex_date = self._parse_nse_action_date(row.get("exDate"))
                if ex_date is None or ex_date < since:
                    continue
                subject = str(row.get("subject", "")).strip()
                action_type, ratio = _parse_corporate_action_ratio(subject)
                actions.append(
                    RawCorporateAction(
                        symbol=symbol,
                        ex_date=ex_date,
                        action_type=action_type,
                        ratio=ratio,
                        raw_subject=subject,
                    )
                )
            except (KeyError, ValueError, TypeError) as exc:
                _logger.warning(
                    "bhavcopy_corporate_action_row_skipped", symbol=symbol, error=str(exc)
                )
        return actions

    # ── Private helpers ───────────────────────────────────────────────────

    @staticmethod
    def _num_or_none(value: Any) -> Decimal | None:
        """Convert a numeric bhavcopy cell to ``Decimal``, or ``None`` if blank/NaN."""
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return None

    @staticmethod
    def _to_decimal(value: Any) -> Decimal:
        """Safely convert a value to ``Decimal``, defaulting to ``0``."""
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return Decimal("0")
        try:
            return Decimal(str(value))
        except (ValueError, TypeError):
            return Decimal("0")

    @staticmethod
    def _to_date(value: Any) -> date | None:
        """Parse a date from the various formats nsemine returns."""
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, pd.Timestamp):
            result: date = value.date()
            return result
        return None

    @staticmethod
    def _parse_nse_action_date(value: Any) -> date | None:
        """Parse NSE's corporate-actions ``exDate`` format (e.g. ``"05-Jun-2026"``)."""
        if not value or not isinstance(value, str) or value.strip() == "-":
            return None
        try:
            return datetime.strptime(value.strip(), "%d-%b-%Y").date()
        except ValueError:
            return None
