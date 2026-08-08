"""Period-correct-split symbol resolution (RP-012 §3, step 3).

Pure, I/O-free resolution (ADR-009) of a *symbol as it stood on a session date*
to the security whose ``[listing_date, delisting_date]`` interval contains that
date. This is the temporally-correct counterpart to a flat symbol-string join:
when a ticker is reused across a rename/handoff, a flat join silently attributes
every historical bar to whichever security currently holds the ticker; interval
containment attributes each bar to the security that actually held the ticker on
that date.

Resolution rules (exactly as research specified):

* **Interval containment** — resolve ``(symbol, D)`` to the unique security whose
  ``[listing, COALESCE(delisting, sentinel)]`` interval contains ``D``.
* **Zero-interval handoff gap** — ``D`` falls in a gap between two intervals of
  the same symbol (predecessor delisted before successor listed): resolve to the
  nearest interval boundary and mark the outcome ``BOUNDARY_GAP`` so it can be
  counted as a documented residual category rather than silently dropped.
* **Multiple-interval overlap** — two intervals for the same symbol both contain
  ``D``: a data-integrity defect. Return ``OVERLAP`` with no ``security_id`` so
  the caller logs and excludes it, never guessing.

The instrument-master precondition this rule presupposes — that the master
carries *dated symbol intervals* (a rename-linkage / historical-ticker table),
so a single symbol can map to more than one dated security row — does not hold
in the current master, where symbol↔security and ISIN↔security are both strictly
1:1. The rule is therefore correct and available but has an empty domain today;
its true unblock is the rename-linkage map (a logged backlog item), not this
resolver. Callers build ``intervals_by_symbol`` from whatever dated-interval
source exists.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class PeriodResolutionOutcome(StrEnum):
    """How a ``(symbol, date)`` resolved under interval containment (aggregatable)."""

    CONTAINED = "contained"
    BOUNDARY_GAP = "boundary_gap"
    OVERLAP = "overlap"
    UNKNOWN_SYMBOL = "unknown_symbol"


@dataclass(frozen=True, slots=True)
class SymbolInterval:
    """A security's trading interval for one symbol; ``end=None`` means still active."""

    security_id: int
    start: date
    end: date | None

    def contains(self, on_date: date) -> bool:
        """Whether ``on_date`` lies within ``[start, end]`` (``end=None`` = open-ended)."""
        if on_date < self.start:
            return False
        return self.end is None or on_date <= self.end


@dataclass(frozen=True, slots=True)
class PeriodResolution:
    """The outcome of resolving one ``(symbol, date)`` under interval containment."""

    security_id: int | None
    outcome: PeriodResolutionOutcome


def resolve_period_correct(
    symbol: str,
    on_date: date,
    intervals_by_symbol: Mapping[str, Sequence[SymbolInterval]],
) -> PeriodResolution:
    """Resolve ``(symbol, on_date)`` to the interval-correct security (pure).

    Args:
        symbol: The period-correct ticker as printed on ``on_date``.
        on_date: The session date of the bar being resolved.
        intervals_by_symbol: Map of symbol → its (possibly multiple) trading
            intervals across rename chains, in any order.

    Returns:
        A :class:`PeriodResolution`. On a handoff gap, ``security_id`` is the
        nearest-boundary security and ``outcome`` is ``BOUNDARY_GAP``; on an
        overlap, ``security_id`` is ``None`` and ``outcome`` is ``OVERLAP``.
    """
    intervals = intervals_by_symbol.get(symbol)
    if not intervals:
        return PeriodResolution(None, PeriodResolutionOutcome.UNKNOWN_SYMBOL)

    containing = [iv for iv in intervals if iv.contains(on_date)]
    if len(containing) == 1:
        return PeriodResolution(containing[0].security_id, PeriodResolutionOutcome.CONTAINED)
    if len(containing) > 1:
        return PeriodResolution(None, PeriodResolutionOutcome.OVERLAP)

    # No interval contains the date — resolve to the nearest boundary (handoff gap).
    nearest = min(intervals, key=lambda iv: _distance_to_interval(iv, on_date))
    return PeriodResolution(nearest.security_id, PeriodResolutionOutcome.BOUNDARY_GAP)


def _distance_to_interval(interval: SymbolInterval, on_date: date) -> int:
    """Absolute day-distance from ``on_date`` to the interval (0 if inside)."""
    if on_date < interval.start:
        return (interval.start - on_date).days
    if interval.end is not None and on_date > interval.end:
        return (on_date - interval.end).days
    return 0
