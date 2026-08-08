"""Unit tests for RP-012 §3.3 survivorship classification."""

from __future__ import annotations

from datetime import date

from momentum25.domain.research.survivorship import (
    GAP_THRESHOLD_TRADING_DAYS,
    classify_survivorship,
)


def test_active_security_through_panel_end() -> None:
    """A security trading at panel end (0 days absent) is active, no delisting."""
    cls = classify_survivorship(date(2019, 9, 30), date(2024, 7, 5), 0)
    assert cls.delisted is False
    assert cls.delisting_date is None
    assert cls.listing_date == date(2019, 9, 30)
    assert cls.last_trade_date == date(2024, 7, 5)


def test_short_final_gap_is_not_a_delisting() -> None:
    """A final absence below the threshold is illiquidity, not a delisting."""
    cls = classify_survivorship(
        date(2019, 9, 30), date(2024, 5, 1), GAP_THRESHOLD_TRADING_DAYS - 1
    )
    assert cls.delisted is False
    assert cls.delisting_date is None


def test_long_final_gap_is_a_delisting() -> None:
    """An absence at/above the threshold through panel end is a delisting."""
    cls = classify_survivorship(
        date(2019, 9, 30), date(2022, 1, 3), GAP_THRESHOLD_TRADING_DAYS
    )
    assert cls.delisted is True
    assert cls.delisting_date == date(2022, 1, 3)
    assert cls.last_trade_date == date(2022, 1, 3)


def test_threshold_is_exact_boundary() -> None:
    """Exactly ``GAP_THRESHOLD_TRADING_DAYS`` absent counts as delisted."""
    below = classify_survivorship(date(2019, 9, 30), date(2022, 1, 3), 59)
    at = classify_survivorship(date(2019, 9, 30), date(2022, 1, 3), 60)
    assert below.delisted is False
    assert at.delisted is True
