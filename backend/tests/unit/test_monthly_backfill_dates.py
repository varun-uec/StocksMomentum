"""Date-grid tests for the monthly forward-returns backfill driver."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from monthly_forward_returns_backfill import (  # noqa: E402
    WINDOW_END,
    WINDOW_START,
    month_end_targets,
    snap_to_trading_dates,
)


def test_month_end_targets_are_last_calendar_days_within_window() -> None:
    targets = month_end_targets(date(2020, 11, 1), date(2021, 3, 1))
    assert targets == [
        date(2020, 11, 30),
        date(2020, 12, 31),
        date(2021, 1, 31),
        date(2021, 2, 28),
    ]


def test_production_window_spans_the_expected_run_count() -> None:
    # 2020-11 through 2026-02 inclusive: 64 monthly runs. One short of the
    # review's ~65 because the 277-session indicator warm-up pushes the first
    # screenable month-end from 2020-10 to 2020-11 (see WINDOW_START).
    assert len(month_end_targets(WINDOW_START, WINDOW_END)) == 64


def test_snap_moves_back_to_the_latest_prior_session_and_collapses_duplicates() -> None:
    trading = [date(2021, 1, 28), date(2021, 1, 29), date(2021, 2, 26)]
    # 2021-01-31 is a Sunday -> snaps back to the 29th; 2021-02-28 -> the 26th.
    assert snap_to_trading_dates(
        [date(2021, 1, 31), date(2021, 2, 28)], trading
    ) == [date(2021, 1, 29), date(2021, 2, 26)]
    # Two targets resolving to the same session yield one run date.
    assert snap_to_trading_dates(
        [date(2021, 1, 31), date(2021, 2, 1)], [date(2021, 1, 29)]
    ) == [date(2021, 1, 29)]


def test_targets_before_any_session_are_dropped_not_guessed() -> None:
    assert snap_to_trading_dates([date(2020, 1, 31)], [date(2021, 1, 29)]) == []
