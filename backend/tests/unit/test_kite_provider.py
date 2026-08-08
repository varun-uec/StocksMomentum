"""Kite Connect adapter (Phase 5.2) — mapping, rate limiting and error handling.

Exercised against a fake :class:`KiteHttpClient`; no live Kite credentials exist
in this platform, so the HTTP boundary itself (``HttpxKiteClient``) is verified
only by inspection. Payload shapes below are copied from the published Kite
Connect v3 documentation examples.
"""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pytest

from momentum25.infrastructure.providers.kite import (
    HttpxKiteClient,
    KiteConnectProvider,
    KiteError,
    KiteTokenExpiredError,
    exchange_request_token,
    kite_login_url,
    parse_candles,
    session_checksum,
)

INSTRUMENTS_CSV = (
    "instrument_token,exchange_token,tradingsymbol,name,last_price,expiry,strike,"
    "tick_size,lot_size,instrument_type,segment,exchange\n"
    "408065,1594,INFY,INFOSYS,0,,,0.05,1,EQ,NSE,NSE\n"
    "738561,2885,RELIANCE,RELIANCE INDUSTRIES,0,,,0.05,1,EQ,NSE,NSE\n"
    "5720322,22345,NIFTY15DECFUT,,78.0,2015-12-31,,0.05,75,FUT,NFO-FUT,NFO\n"
    "134657,526,INFY,INFOSYS,0,,,0.05,1,EQ,BSE,BSE\n"
)

CANDLES: dict[str, Any] = {
    "status": "success",
    "data": {
        "candles": [
            ["2017-12-15T00:00:00+0530", 1704.5, 1705, 1699.25, 1702.8, 2499],
            ["2017-12-14T00:00:00+0530", 1700, 1710, 1690, 1695.55, 1000],
        ]
    },
}


class FakeKiteClient:
    """Records calls and replays canned documented payloads."""

    def __init__(self, json_body: Any = None, text_body: str = INSTRUMENTS_CSV) -> None:
        self.json_body = json_body if json_body is not None else CANDLES
        self.text_body = text_body
        self.json_calls: list[tuple[str, dict[str, str] | None]] = []
        self.text_calls: list[str] = []

    async def get_json(self, path: str, params: dict[str, str] | None = None) -> Any:
        self.json_calls.append((path, params))
        return self.json_body

    async def get_text(self, path: str) -> str:
        self.text_calls.append(path)
        return self.text_body


def test_login_url_and_checksum_match_the_documented_flow() -> None:
    assert kite_login_url("abc123") == "https://kite.zerodha.com/connect/login?v=3&api_key=abc123"
    assert session_checksum("k", "r", "s") == hashlib.sha256(b"krs").hexdigest()


async def test_instrument_master_keeps_only_equities_of_the_bound_exchange() -> None:
    provider = KiteConnectProvider(FakeKiteClient(), exchange="NSE")

    instruments = await provider.fetch_instrument_master()

    assert [i.symbol for i in instruments] == ["INFY", "RELIANCE"]
    # The Kite instruments dump publishes no ISIN column — never fabricated.
    assert all(i.isin is None for i in instruments)


async def test_historical_request_targets_the_right_token_interval_and_window() -> None:
    client = FakeKiteClient()
    provider = KiteConnectProvider(client, exchange="NSE")

    bars = await provider.fetch_historical_bars("infy", date(2017, 12, 14), date(2017, 12, 15))

    assert client.text_calls == ["/instruments/NSE"]
    path, params = client.json_calls[0]
    assert path == "/instruments/historical/408065/day"
    assert params == {"from": "2017-12-14 00:00:00", "to": "2017-12-15 23:59:59"}
    assert [b.date for b in bars] == [date(2017, 12, 14), date(2017, 12, 15)]
    assert bars[1].open == Decimal("1704.5")
    assert bars[1].close == Decimal("1702.8")
    assert bars[1].volume == 2499
    assert bars[1].symbol == "INFY"


async def test_bse_exchange_selects_the_bse_instrument_token() -> None:
    client = FakeKiteClient()
    provider = KiteConnectProvider(client, exchange="BSE")

    await provider.fetch_historical_bars("INFY", date(2017, 12, 15))

    assert client.json_calls[0][0] == "/instruments/historical/134657/day"


async def test_instrument_map_is_loaded_once_not_per_symbol() -> None:
    client = FakeKiteClient()
    provider = KiteConnectProvider(client, exchange="NSE")

    await provider.fetch_eod_for_symbols(["INFY", "RELIANCE"], date(2017, 12, 15))

    assert client.text_calls == ["/instruments/NSE"]
    assert len(client.json_calls) == 2


async def test_unknown_symbol_yields_no_bars_and_no_request() -> None:
    client = FakeKiteClient()
    provider = KiteConnectProvider(client, exchange="NSE")

    assert await provider.fetch_historical_bars("NOSUCH", date(2017, 12, 15)) == []
    assert client.json_calls == []


def test_malformed_candles_are_skipped_never_defaulted() -> None:
    bars = parse_candles({"data": {"candles": [["2017-12-15T00:00:00+0530", 1, 2, 3]]}}, "X")
    assert bars == []
    assert parse_candles({}, "X") == []


async def test_token_expiry_surfaces_as_its_own_error_type() -> None:
    class ExpiredClient(FakeKiteClient):
        async def get_json(self, path: str, params: dict[str, str] | None = None) -> Any:
            raise KiteTokenExpiredError("Invalid session", error_type="TokenException", status=403)

    provider = KiteConnectProvider(ExpiredClient(), exchange="NSE")

    with pytest.raises(KiteTokenExpiredError):
        await provider.fetch_historical_bars("INFY", date(2017, 12, 15))


async def test_http_client_maps_403_to_token_expiry_and_500_to_general_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/boom"):
            return httpx.Response(500, json={"error_type": "GeneralException", "message": "bad"})
        return httpx.Response(403, json={"error_type": "TokenException", "message": "expired"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        client = HttpxKiteClient("key", "token", client=http)
        with pytest.raises(KiteTokenExpiredError):
            await client.get_json("/user/profile")
        with pytest.raises(KiteError) as exc:
            await client.get_json("/boom")
    assert exc.value.error_type == "GeneralException"
    assert exc.value.status == 500


async def test_http_client_signs_every_request_as_documented() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.headers)
        return httpx.Response(200, json={"status": "success"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        await HttpxKiteClient("mykey", "mytoken", client=http).get_json("/user/profile")

    assert seen["authorization"] == "token mykey:mytoken"
    assert seen["x-kite-version"] == "3"


async def test_request_token_exchange_posts_the_checksum_and_returns_access_token() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content.decode()
        captured["path"] = request.url.path
        return httpx.Response(200, json={"data": {"access_token": "ACCESS"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        token = await exchange_request_token("k", "s", "r", client=http)

    assert token == "ACCESS"
    assert captured["path"] == "/session/token"
    assert f"checksum={session_checksum('k', 'r', 's')}" in captured["body"]


async def test_missing_access_token_in_session_response_is_an_error_not_empty_string() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"data": {}}))
    ) as http:
        with pytest.raises(KiteError):
            await exchange_request_token("k", "s", "r", client=http)


async def test_historical_calls_are_throttled_to_the_documented_three_per_second() -> None:
    import time

    provider = KiteConnectProvider(FakeKiteClient(), exchange="NSE")
    started = time.monotonic()
    await provider.fetch_eod_for_symbols(["INFY", "RELIANCE", "INFY"], date(2017, 12, 15))
    elapsed = time.monotonic() - started

    # 3 historical calls at 3 req/s ⇒ at least two inter-call gaps of 1/3 s.
    assert elapsed >= 2 / 3
