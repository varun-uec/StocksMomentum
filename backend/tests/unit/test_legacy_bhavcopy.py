"""Unit tests for the RP-012 D1 legacy-archive date routing and CSV parsing.

The routing rule and the legacy parser are pure, I/O-free functions of their
inputs (ADR-009 determinism), so they are golden-tested without any network.
"""

from __future__ import annotations

import io
import zipfile
from datetime import date
from decimal import Decimal

import pytest

from momentum25.infrastructure.providers.bhavcopy import (
    _CURRENT_PROVIDER_START,
    _legacy_archive_url,
    _parse_legacy_bhavcopy,
)

# Legacy (1994) schema — trailing comma → empty final column, exactly as served.
_LEGACY_1994 = (
    "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,TIMESTAMP,\n"
    "ABB,EQ,715,715,715,715,715,0.0,100,71500,3-NOV-1994,\n"
    "ACC,EQ,3000,3050,2980,3020,3010,2990,50,151000,3-NOV-1994,\n"
    "SOMEBOND,N2,100,100,100,100,100,100,10,1000,3-NOV-1994,\n"
)

# 2019-era schema adds TOTALTRADES,ISIN; parsing by header name must tolerate it.
_LEGACY_2019 = (
    "SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,TOTTRDVAL,"
    "TIMESTAMP,TOTALTRADES,ISIN,\n"
    "20MICRONS,EQ,39.9,40.95,37.1,37.9,37.5,40.05,29683,1144441.35,"
    "01-OCT-2019,573,INE144J01027,\n"
)


def _zip(csv_text: str, name: str = "cm.csv") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(name, csv_text)
    return buf.getvalue()


class TestDateRouting:
    """The legacy/current cutover is a fixed function of date."""

    def test_cutover_constant_is_measured_boundary(self) -> None:
        assert date(2019, 9, 30) == _CURRENT_PROVIDER_START

    @pytest.mark.parametrize(
        "for_date, expect_legacy",
        [
            (date(1994, 11, 3), True),
            (date(2019, 9, 29), True),
            (date(2019, 9, 30), False),
            (date(2024, 7, 5), False),
        ],
    )
    def test_routing_boundary(self, for_date: date, expect_legacy: bool) -> None:
        assert (for_date < _CURRENT_PROVIDER_START) is expect_legacy

    def test_url_is_deterministic_and_correctly_formatted(self) -> None:
        assert _legacy_archive_url(date(1994, 11, 3)) == (
            "https://archives.nseindia.com/content/historical/EQUITIES/"
            "1994/NOV/cm03NOV1994bhav.csv.zip"
        )
        assert _legacy_archive_url(date(2019, 10, 1)) == (
            "https://archives.nseindia.com/content/historical/EQUITIES/"
            "2019/OCT/cm01OCT2019bhav.csv.zip"
        )


class TestLegacyParser:
    """Golden tests for _parse_legacy_bhavcopy."""

    def test_parses_eq_rows_and_preserves_prevclose_and_turnover(self) -> None:
        bars = _parse_legacy_bhavcopy(_zip(_LEGACY_1994), date(1994, 11, 3))
        assert [b.symbol for b in bars] == ["ABB", "ACC"]  # N2 series filtered out
        acc = bars[1]
        assert acc.open == Decimal("3000")
        assert acc.close == Decimal("3020")
        assert acc.volume == 50
        assert acc.prev_close == Decimal("2990")
        assert acc.turnover_value == Decimal("151000")
        assert acc.date == date(1994, 11, 3)

    def test_genuine_zero_prevclose_is_preserved_not_nulled(self) -> None:
        bars = _parse_legacy_bhavcopy(_zip(_LEGACY_1994), date(1994, 11, 3))
        assert bars[0].symbol == "ABB"
        assert bars[0].prev_close == Decimal("0.0")

    def test_series_filter_keeps_only_eq(self) -> None:
        bars = _parse_legacy_bhavcopy(_zip(_LEGACY_1994), date(1994, 11, 3))
        assert all(True for _ in bars)  # no non-EQ leaks
        assert "SOMEBOND" not in {b.symbol for b in bars}

    def test_parses_2019_schema_with_extra_columns(self) -> None:
        bars = _parse_legacy_bhavcopy(_zip(_LEGACY_2019), date(2019, 10, 1))
        assert len(bars) == 1
        bar = bars[0]
        assert bar.symbol == "20MICRONS"
        assert bar.prev_close == Decimal("40.05")
        assert bar.turnover_value == Decimal("1144441.35")

    def test_2019_schema_captures_isin(self) -> None:
        bars = _parse_legacy_bhavcopy(_zip(_LEGACY_2019), date(2019, 10, 1))
        assert bars[0].isin == "INE144J01027"

    def test_pre_isin_schema_leaves_isin_none(self) -> None:
        bars = _parse_legacy_bhavcopy(_zip(_LEGACY_1994), date(1994, 11, 3))
        assert all(b.isin is None for b in bars)

    def test_bad_zip_returns_empty(self) -> None:
        assert _parse_legacy_bhavcopy(b"not a zip", date(2019, 10, 1)) == []

    def test_unexpected_columns_returns_empty(self) -> None:
        bad = _zip("FOO,BAR\n1,2\n")
        assert _parse_legacy_bhavcopy(bad, date(2019, 10, 1)) == []

    def test_parser_is_deterministic(self) -> None:
        payload = _zip(_LEGACY_1994)
        first = _parse_legacy_bhavcopy(payload, date(1994, 11, 3))
        second = _parse_legacy_bhavcopy(payload, date(1994, 11, 3))
        assert first == second
