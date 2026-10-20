"""Validation for the normalized, offline CSV import boundary."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from momentum25.application.use_cases.import_market_data import (
    check_bar_dates,
    parse_actions_csv,
    parse_benchmark_csv,
    parse_eod_csv,
)


def _csv(path: Path, contents: str) -> Path:
    path.write_text(contents, encoding="utf-8")
    return path


def test_parse_eod_csv_normalizes_symbols_and_keeps_source_fields(tmp_path: Path) -> None:
    path = _csv(
        tmp_path / "bars.csv",
        "symbol,date,open,high,low,close,volume,name,exchange,isin,listing_date,prev_close,turnover_value\n"
        "reliance,2026-01-02,100,105,98,103,1200,Reliance,NSE,INE002A01018,1977-11-08,99,123600\n",
    )

    securities, bars = parse_eod_csv(path)

    assert [str(securities[0].symbol), securities[0].name, securities[0].isin] == [
        "RELIANCE",
        "Reliance",
        "INE002A01018",
    ]
    assert bars["RELIANCE"][0].turnover_value == 123600
    assert bars["RELIANCE"][0].prev_close == 99


@pytest.mark.parametrize(
    ("contents", "message"),
    [
        (
            "symbol,date,open,high,low,close,volume\nX,2026-01-02,100,99,98,100,1\n",
            "OHLC values violate high/low bounds",
        ),
        (
            "symbol,date,open,high,low,close,volume\nX,2026-01-02,100,105,95,100,1\nX,2026-01-02,100,105,95,100,1\n",
            "duplicate symbol/date",
        ),
        (
            "symbol,date,open,high,low,close,volume\nX,2026-02-30,100,105,95,100,1\n",
            "expected YYYY-MM-DD",
        ),
        (
            "symbol,date,open,high,low,close,volume\nX,2026-01-02,100,105,95,100,-1\n",
            "non-negative integer",
        ),
    ],
)
def test_parse_eod_csv_rejects_invalid_or_ambiguous_rows(
    tmp_path: Path, contents: str, message: str
) -> None:
    path = _csv(tmp_path / "bad.csv", contents)
    with pytest.raises(ValueError, match=message):
        parse_eod_csv(path)


def test_parse_actions_csv_accepts_unpriced_actions_and_rejects_zero_ratio(
    tmp_path: Path,
) -> None:
    actions = _csv(
        tmp_path / "actions.csv",
        "symbol,ex_date,type,ratio,raw_subject\nX,2026-01-02,dividend,,cash dividend\n",
    )
    assert parse_actions_csv(actions)["X"][0].ratio is None

    bad = _csv(
        tmp_path / "bad-actions.csv",
        "symbol,ex_date,type,ratio\nX,2026-01-02,split,0\n",
    )
    with pytest.raises(ValueError, match="finite positive"):
        parse_actions_csv(bad)


def test_parse_benchmark_csv_requires_one_code_and_unique_dates(tmp_path: Path) -> None:
    path = _csv(
        tmp_path / "benchmark.csv",
        "index_code,date,close\nNIFTY500,2026-01-02,25000\nNIFTY500,2026-01-05,25100\n",
    )
    code, bars = parse_benchmark_csv(path)
    assert code == "NIFTY500" and len(bars) == 2

    duplicate = _csv(
        tmp_path / "duplicate.csv",
        "index_code,date,close\nNIFTY500,2026-01-02,25000\nNIFTY500,2026-01-02,25100\n",
    )
    with pytest.raises(ValueError, match="duplicate benchmark date"):
        parse_benchmark_csv(duplicate)


class _Calendar:
    """Weekdays are sessions except one listed holiday."""

    def is_session(self, day: date) -> bool:
        return day.weekday() < 5 and day != date(2026, 10, 20)


@pytest.mark.parametrize(
    ("bar_date", "message"),
    [
        ("2026-10-20", "not an exchange trading session"),  # holiday
        ("2026-10-17", "not an exchange trading session"),  # Saturday
        ("2026-10-21", "dated after today"),  # a session, but in the future
    ],
)
def test_check_bar_dates_rejects_non_session_and_future_rows(
    tmp_path: Path, bar_date: str, message: str
) -> None:
    # Regression R3-B: one such row became the latest stored date, and the next
    # screen dropped every other security as no_bar_on_trading_date.
    path = _csv(
        tmp_path / "bars.csv",
        f"symbol,date,open,high,low,close,volume\nX,2026-10-19,1,1,1,1,1\nX,{bar_date},1,1,1,1,1\n",
    )
    _, bars = parse_eod_csv(path)
    with pytest.raises(ValueError, match=message):
        check_bar_dates(bars, date(2026, 10, 20), _Calendar())


def test_check_bar_dates_accepts_sessions_up_to_today(tmp_path: Path) -> None:
    path = _csv(
        tmp_path / "bars.csv",
        "symbol,date,open,high,low,close,volume\nX,2026-10-16,1,1,1,1,1\nX,2026-10-19,1,1,1,1,1\n",
    )
    _, bars = parse_eod_csv(path)
    check_bar_dates(bars, date(2026, 10, 19), _Calendar())
    check_bar_dates(bars, date(2026, 10, 19))  # without a calendar only the future is checked
