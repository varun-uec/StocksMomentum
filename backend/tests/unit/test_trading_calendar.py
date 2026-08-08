"""Unit tests for staleness classification (Phase 1.5)."""

from __future__ import annotations

from datetime import date

from momentum25.domain.research.trading_calendar import DataFreshness, assess_freshness


def test_no_data_ever_is_stale() -> None:
    result = assess_freshness(None, date(2026, 8, 7), [])
    assert result.classification == DataFreshness.STALE
    assert result.latest_bar_date is None


def test_no_sessions_since_latest_bar_is_fresh() -> None:
    latest = date(2026, 8, 7)
    result = assess_freshness(latest, latest, [])
    assert result.classification == DataFreshness.FRESH
    assert result.sessions_missed == 0


def test_as_of_is_the_only_missed_session_is_market_closed_not_stale() -> None:
    # Latest bar Friday; as_of is the next session (Monday) and nothing else
    # was missed in between -- today just hasn't been ingested yet.
    latest = date(2026, 8, 7)
    as_of = date(2026, 8, 10)
    result = assess_freshness(latest, as_of, [as_of])
    assert result.classification == DataFreshness.MARKET_CLOSED
    assert result.sessions_missed == 0


def test_missed_sessions_before_as_of_is_stale() -> None:
    latest = date(2026, 8, 3)
    as_of = date(2026, 8, 10)
    sessions_since = [date(2026, 8, 4), date(2026, 8, 5), date(2026, 8, 6), date(2026, 8, 7), as_of]
    result = assess_freshness(latest, as_of, sessions_since)
    assert result.classification == DataFreshness.STALE
    assert result.sessions_missed == 4


def test_missed_sessions_not_including_as_of_is_stale() -> None:
    latest = date(2026, 8, 3)
    as_of = date(2026, 8, 9)  # a holiday, not itself a session
    sessions_since = [date(2026, 8, 4), date(2026, 8, 5), date(2026, 8, 6), date(2026, 8, 7)]
    result = assess_freshness(latest, as_of, sessions_since)
    assert result.classification == DataFreshness.STALE
    assert result.sessions_missed == 4
