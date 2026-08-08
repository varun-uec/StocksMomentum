"""Trading-session staleness classification (Phase 1.5).

Pure, I/O-free: the caller resolves sessions from a :class:`TradingCalendar`
port and passes them in, so this module has no infrastructure dependency and
stays inside the "Domain is pure" import-linter contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class DataFreshness(StrEnum):
    """Classification of how current the latest persisted bar is."""

    FRESH = "FRESH"
    MARKET_CLOSED = "MARKET_CLOSED"
    STALE = "STALE"


@dataclass(frozen=True, slots=True)
class FreshnessAssessment:
    """Result of comparing the latest persisted bar against expected sessions."""

    classification: DataFreshness
    sessions_missed: int
    latest_bar_date: date | None
    as_of: date


def assess_freshness(
    latest_bar_date: date | None,
    as_of: date,
    sessions_since: list[date],
) -> FreshnessAssessment:
    """Classify data freshness given the sessions expected since the last bar.

    Args:
        latest_bar_date: The newest persisted bar date, or ``None`` if no data.
        as_of: The reference "now" date.
        sessions_since: Trading sessions strictly after ``latest_bar_date`` and
            up to and including ``as_of`` (empty if the market has not opened
            since the last bar -- e.g. a holiday or weekend).

    Returns:
        A :class:`FreshnessAssessment`. ``MARKET_CLOSED`` means no session was
        missed -- the gap is expected, not a data problem. ``STALE`` means at
        least one session that should have produced a bar did not.
    """
    if latest_bar_date is None:
        return FreshnessAssessment(DataFreshness.STALE, 0, None, as_of)

    missed = len(sessions_since)
    if missed == 0:
        return FreshnessAssessment(DataFreshness.FRESH, 0, latest_bar_date, as_of)

    # The final session in sessions_since is "as_of" itself if as_of is a
    # trading day still in progress or not yet ingested for -- that alone is
    # not staleness. Anything before it being missing is.
    trailing_missed = missed - 1 if sessions_since[-1] == as_of else missed
    if trailing_missed <= 0:
        return FreshnessAssessment(DataFreshness.MARKET_CLOSED, 0, latest_bar_date, as_of)
    return FreshnessAssessment(DataFreshness.STALE, trailing_missed, latest_bar_date, as_of)
