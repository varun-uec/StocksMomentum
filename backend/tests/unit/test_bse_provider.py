"""BSE bhavcopy parsing (Phase 5.1 / RP-014).

The UDiFF fixture is an unmodified 4-row slice of a real BSE UDiFF equity
bhavcopy (2026-08-06), header and quoting intact — so a schema change at BSE
breaks these tests rather than silently producing wrong numbers. The legacy
fixture is an unmodified 5-row slice of a real legacy EQ_CSV bhavcopy
(2008-01-02) covering both the equity rows and the non-equity rows the parser
must exclude.
"""

from __future__ import annotations

import io
import zipfile
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from momentum25.infrastructure.providers.bse_bhavcopy import (
    BSE_LEGACY_START,
    UDIFF_START,
    BSEBhavcopyProvider,
    bse_archive_url,
    bse_bhavcopy_url,
    bse_legacy_bhavcopy_url,
    parse_bse_bhavcopy,
    parse_bse_instruments,
    parse_bse_legacy_bhavcopy,
)

FIXTURE = Path(__file__).parent.parent / "fixtures" / "bse_bhavcopy_20260806_sample.csv"
SESSION = date(2026, 8, 6)

LEGACY_FIXTURE = (
    Path(__file__).parent.parent / "fixtures" / "bse_bhavcopy_20080102_legacy_sample.csv"
)
LEGACY_SESSION = date(2008, 1, 2)


def payload() -> bytes:
    return FIXTURE.read_bytes()


def legacy_zip_payload() -> bytes:
    """Wrap the legacy fixture in the ZIP container BSE actually publishes."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as arc:
        arc.writestr("EQ020108.CSV", LEGACY_FIXTURE.read_bytes())
    return buffer.getvalue()


def test_url_matches_the_published_bse_filename_convention() -> None:
    assert bse_bhavcopy_url(date(2026, 8, 6)) == (
        "https://www.bseindia.com/download/BhavCopy/Equity/"
        "BhavCopy_BSE_CM_0_0_0_20260806_F_0000.CSV"
    )


def test_legacy_url_matches_the_published_bse_filename_convention() -> None:
    assert bse_legacy_bhavcopy_url(date(2008, 1, 2)) == (
        "https://www.bseindia.com/download/BhavCopy/Equity/EQ020108_CSV.ZIP"
    )


def test_archive_routes_by_measured_availability_windows() -> None:
    # Before the legacy archive begins there is no URL at all.
    assert bse_archive_url(date(1999, 1, 4)) is None
    assert bse_archive_url(date(2006, 2, 28)) is None
    # Legacy EQ_CSV runs from its measured first file through the last one.
    assert bse_archive_url(date(2006, 3, 1)) == bse_legacy_bhavcopy_url(date(2006, 3, 1))
    assert bse_archive_url(date(2008, 1, 2)) == bse_legacy_bhavcopy_url(date(2008, 1, 2))
    assert bse_archive_url(date(2023, 12, 29)) == bse_legacy_bhavcopy_url(date(2023, 12, 29))
    # From UDiFF's first date the current provider takes over.
    assert bse_archive_url(date(2024, 1, 2)) == bse_bhavcopy_url(date(2024, 1, 2))


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


# ── RP-014: legacy EQ_CSV parser ───────────────────────────────────────────


def test_legacy_bars_map_the_documented_columns_exactly() -> None:
    bars = {
        bar.symbol: bar
        for bar in parse_bse_legacy_bhavcopy(legacy_zip_payload(), LEGACY_SESSION)
    }

    assert len(bars) == 3
    assert bars["21ST CEN.MGM"].date == LEGACY_SESSION
    assert bars["21ST CEN.MGM"].open == Decimal("103.10")
    assert bars["21ST CEN.MGM"].high == Decimal("113.75")
    assert bars["21ST CEN.MGM"].low == Decimal("102.95")
    assert bars["21ST CEN.MGM"].close == Decimal("113.75")
    assert bars["21ST CEN.MGM"].volume == 112707
    assert bars["21ST CEN.MGM"].prev_close == Decimal("108.35")
    assert bars["21ST CEN.MGM"].turnover_value == Decimal("12427853.00")
    # Legacy files carry no ISIN; identity rides on the numeric SC_CODE.
    assert bars["21ST CEN.MGM"].isin is None
    assert bars["21ST CEN.MGM"].native_code == "526921"
    assert bars["3M INDIA LTD"].native_code == "523395"


def test_legacy_parser_drops_non_equity_scrips() -> None:
    # The real 2008 session mixes preference shares (P), debt (B) and debentures
    # (D) with equities (Q); only Q rows are bars.
    symbols = {
        bar.symbol
        for bar in parse_bse_legacy_bhavcopy(legacy_zip_payload(), LEGACY_SESSION)
    }
    assert "ISPAT PR SH" not in symbols
    assert "6.75% US-64" not in symbols


def test_legacy_blank_cells_become_zero_or_none_not_errors() -> None:
    # A blank CLOSE means the row is not a tradeable equity session record and
    # is dropped; blank OHLC/volume cells coerce to 0, blank PREVCLOSE and
    # NET_TURNOV stay None.
    payload_bytes = (
        b"SC_CODE,SC_NAME,SC_GROUP,SC_TYPE,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,NO_TRADES,NO_OF_SHRS,NET_TURNOV,TDCLOINDI\n"
        b"512609,BLAH ,B ,Q,,,,42.50,,, , ,900.00,\n"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as arc:
        arc.writestr("EQ020108.CSV", payload_bytes)
    bar = parse_bse_legacy_bhavcopy(buffer.getvalue(), LEGACY_SESSION)[0]
    assert bar.open == Decimal("0")
    assert bar.high == Decimal("0")
    assert bar.low == Decimal("0")
    assert bar.close == Decimal("42.50")
    assert bar.volume == 0
    assert bar.prev_close is None
    assert bar.turnover_value == Decimal("900.00")


def test_legacy_blank_close_rows_are_dropped() -> None:
    payload_bytes = (
        b"SC_CODE,SC_NAME,SC_GROUP,SC_TYPE,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,NO_TRADES,NO_OF_SHRS,NET_TURNOV,TDCLOINDI\n"
        b"512609,BLAH ,B ,Q,,,,42.50,,, , ,900.00,\n"
        b"512610,DEAD ,B ,Q,10.00,11.00,9.50,,,,10,100,900.00,\n"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as arc:
        arc.writestr("EQ020108.CSV", payload_bytes)
    bars = parse_bse_legacy_bhavcopy(buffer.getvalue(), LEGACY_SESSION)
    assert [bar.symbol for bar in bars] == ["BLAH"]


def test_legacy_html_payload_yields_nothing_rather_than_garbage() -> None:
    # BSE answers missing legacy files with HTTP 200 and an HTML page.
    assert parse_bse_legacy_bhavcopy(b"<!DOCTYPE html><html></html>", LEGACY_SESSION) == []


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


def test_archive_windows_are_sane_and_public() -> None:
    # These constants are the measured truth behind routing decisions; the
    # backfill bounds them, so they must never silently drift.
    assert date(2006, 3, 1) == BSE_LEGACY_START
    assert date(2024, 1, 2) == UDIFF_START
    assert BSE_LEGACY_START < UDIFF_START
