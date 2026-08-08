"""Adapter tests for :mod:`infrastructure.calendar.nse_calendar`.

Deliberately avoids asserting specific NSE holiday dates from memory (the same
reasoning that led to deleting the unverifiable Wilder's worked-example test in
Phase 0): everything here is checked against safe, structural invariants of a
trading calendar instead -- a known Sunday is never a session, a known weekday
in a quiet stretch (no major holiday cluster) is a session, and the returned
session count never exceeds the count of weekdays in the range.
"""

from __future__ import annotations

from datetime import date, timedelta

from momentum25.infrastructure.calendar.nse_calendar import get_nse_trading_calendar


def test_a_sunday_is_never_a_session() -> None:
    cal = get_nse_trading_calendar()
    sunday = date(2026, 8, 9)
    assert sunday.weekday() == 6
    assert cal.is_session(sunday) is False


def test_a_quiet_midweek_day_is_a_session() -> None:
    cal = get_nse_trading_calendar()
    wednesday = date(2026, 8, 12)
    assert wednesday.weekday() == 2
    assert cal.is_session(wednesday) is True


def test_sessions_between_never_exceeds_weekday_count() -> None:
    cal = get_nse_trading_calendar()
    start, end = date(2026, 1, 1), date(2026, 3, 31)
    sessions = cal.sessions_between(start, end)

    weekdays = 0
    d = start
    while d <= end:
        if d.weekday() < 5:
            weekdays += 1
        d += timedelta(days=1)

    assert len(sessions) <= weekdays
    assert all(s.weekday() < 5 for s in sessions)
    assert sessions == sorted(sessions)


def test_next_session_is_strictly_after_and_is_a_session() -> None:
    cal = get_nse_trading_calendar()
    friday = date(2026, 8, 7)
    nxt = cal.next_session(friday)
    assert nxt > friday
    assert cal.is_session(nxt)


def test_next_session_accepts_a_non_session_input() -> None:
    """`after` is often "today", which may itself be a weekend/holiday."""
    cal = get_nse_trading_calendar()
    sunday = date(2026, 8, 9)
    assert cal.is_session(sunday) is False
    nxt = cal.next_session(sunday)
    assert nxt > sunday
    assert cal.is_session(nxt)
