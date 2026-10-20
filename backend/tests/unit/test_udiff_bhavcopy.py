"""Unit tests for the dated NSE UDiFF archive route."""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import date
from decimal import Decimal

import pytest

from momentum25.infrastructure.providers.bhavcopy import (
    BhavcopyProvider,
    _parse_udiff_bhavcopy,
    _udiff_bhavcopy_url,
)

_DAY = date(2026, 8, 11)
_FIELDS = [
    "TradDt",
    "FinInstrmTp",
    "ISIN",
    "TckrSymb",
    "SctySrs",
    "OpnPric",
    "HghPric",
    "LwPric",
    "ClsPric",
    "PrvsClsgPric",
    "TtlTradgVol",
    "TtlTrfVal",
]


def _archive(rows: list[dict[str, str]]) -> bytes:
    """Build a small UDiFF archive payload for parser tests."""
    text = io.StringIO()
    writer = csv.DictWriter(text, fieldnames=_FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("bhavcopy.csv", text.getvalue())
    return output.getvalue()


def _row(
    symbol: str,
    *,
    instrument_type: str = "STK",
    series: str = "EQ",
    trade_date: date = _DAY,
) -> dict[str, str]:
    return {
        "TradDt": trade_date.isoformat(),
        "FinInstrmTp": instrument_type,
        "ISIN": "INE002A01018",
        "TckrSymb": symbol,
        "SctySrs": series,
        "OpnPric": "2500.00",
        "HghPric": "2520.00",
        "LwPric": "2490.00",
        "ClsPric": "2510.00",
        "PrvsClsgPric": "2495.00",
        "TtlTradgVol": "1234567",
        "TtlTrfVal": "3098765432.10",
    }


def test_udiff_parser_keeps_only_the_requested_cash_equity_rows() -> None:
    """Cash EQ rows are retained; other series, instruments and dates are excluded."""
    content = _archive(
        [
            _row("RELIANCE"),
            _row("SGBJUN28", series="GB"),
            _row("NIFTY", instrument_type="FUT"),
            _row("OLD", trade_date=date(2026, 8, 10)),
        ]
    )

    bars = _parse_udiff_bhavcopy(content, _DAY, include_extended=True)

    assert len(bars) == 1
    assert bars[0].symbol == "RELIANCE"
    assert bars[0].isin == "INE002A01018"
    assert bars[0].prev_close == Decimal("2495.00")
    assert bars[0].turnover_value == Decimal("3098765432.10")
    assert bars[0].volume == 1234567


def test_udiff_minimal_variant_does_not_expose_extended_fields() -> None:
    """The minimal provider method retains its established field contract."""
    bars = _parse_udiff_bhavcopy(_archive([_row("RELIANCE")]), _DAY, include_extended=False)

    assert bars[0].isin == "INE002A01018"
    assert bars[0].prev_close is None
    assert bars[0].turnover_value is None


class _FakeResponse:
    def __init__(self, status_code: int, content: bytes = b"") -> None:
        self.status_code = status_code
        self.content = content


class _FakeClient:
    def __init__(self, response: _FakeResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, str] | None]] = []

    async def get(self, url: str, *, headers: dict[str, str]) -> _FakeResponse:
        self.calls.append((url, headers))
        return self.response


@pytest.mark.asyncio
async def test_udiff_dates_use_the_dated_archive_and_full_fields() -> None:
    """The provider fetches the exact dated source and preserves full-bar fields."""
    client = _FakeClient(_FakeResponse(200, _archive([_row("RELIANCE")])))
    provider = BhavcopyProvider(client=client)  # type: ignore[arg-type]

    bars = await provider.fetch_eod_full(_DAY)

    assert client.calls[0][0] == _udiff_bhavcopy_url(_DAY)
    assert client.calls[0][1]["Referer"] == "https://www.nseindia.com/"
    assert len(bars) == 1
    assert bars[0].prev_close == Decimal("2495.00")


@pytest.mark.asyncio
async def test_udiff_missing_archive_returns_empty_without_misdating() -> None:
    """A missing archive never falls back to a previous session's bars."""
    client = _FakeClient(_FakeResponse(404))
    provider = BhavcopyProvider(client=client)  # type: ignore[arg-type]

    assert await provider.fetch_eod(_DAY) == []
