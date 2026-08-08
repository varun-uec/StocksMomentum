"""BSE bhavcopy parsing (Phase 5.1).

The fixture is an unmodified 4-row slice of a real BSE UDiFF equity bhavcopy
(2026-08-06), header and quoting intact — so a schema change at BSE breaks these
tests rather than silently producing wrong numbers.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from momentum25.infrastructure.providers.bse_bhavcopy import (
    BSEBhavcopyProvider,
    bse_bhavcopy_url,
    parse_bse_bhavcopy,
    parse_bse_instruments,
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "bse_bhavcopy_20260806_sample.csv"
SESSION = date(2026, 8, 6)


def payload() -> bytes:
    return FIXTURE.read_bytes()


def test_url_matches_the_published_bse_filename_convention() -> None:
    assert bse_bhavcopy_url(date(2026, 8, 6)) == (
        "https://www.bseindia.com/download/BhavCopy/Equity/"
        "BhavCopy_BSE_CM_0_0_0_20260806_F_0000.CSV"
    )


def test_bars_map_the_documented_columns_exactly() -> None:
    bars = {bar.symbol: bar for bar in parse_bse_bhavcopy(payload(), SESSION)}

    reliance = bars["RELIANCE"]
    assert reliance.date == SESSION
    assert reliance.open == Decimal("1283.30")
    assert reliance.high == Decimal("1325.00")
    assert reliance.low == Decimal("1282.00")
    assert reliance.close == Decimal("1325.00")
    assert reliance.volume == 3308316
    assert reliance.prev_close == Decimal("1281.00")
    assert reliance.turnover_value == Decimal("4353493333.00")
    assert reliance.isin == "INE002A01018"


def test_rows_from_another_session_are_dropped_not_misdated() -> None:
    assert parse_bse_bhavcopy(payload(), date(2026, 8, 5)) == []


def test_non_bhavcopy_payload_yields_nothing_rather_than_garbage() -> None:
    # BSE answers an unknown path with HTTP 200 and an HTML page.
    assert parse_bse_bhavcopy(b"<!DOCTYPE html><html></html>", SESSION) == []
    assert parse_bse_instruments(b"<!DOCTYPE html><html></html>", SESSION) == []


def test_instrument_master_carries_isin_name_and_group() -> None:
    instruments = {inst.symbol: inst for inst in parse_bse_instruments(payload(), SESSION)}

    assert instruments["ABB"].isin == "INE117A01022"
    assert instruments["ABB"].name == "ABB INDIA LIMITED"
    assert instruments["ABB"].series == "A"
    # Group B here is an ETF unit (INF... ISIN): retained with its group, never
    # silently classified as equity.
    assert instruments["SETFNIF50"].series == "B"
    assert instruments["ABB"].listing_date is None
    assert list(instruments) == sorted(instruments)


async def test_unverified_endpoints_fail_loudly_instead_of_returning_empty() -> None:
    provider = BSEBhavcopyProvider()
    with pytest.raises(NotImplementedError):
        await provider.fetch_benchmark("SENSEX", SESSION)
    with pytest.raises(NotImplementedError):
        await provider.fetch_corporate_actions("RELIANCE", SESSION)
