"""Confirmed swing detection — the pivot definition every wave count is built on.

A percentage-reversal zigzag: a tracked extreme becomes a pivot only once price
reverses ``threshold_pct`` away from it. This is the platform's single notion of
a swing point; :mod:`momentum25.domain.analytics.chart_patterns` consumes the
same function so the two surfaces cannot drift apart on what a pivot is.

Pure and deterministic. No I/O, no clock, no randomness.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from momentum25.domain.entities.market_data import OHLCVBar

DEFAULT_ZIGZAG_THRESHOLD_PCT = Decimal("5")
"""Reversal size (percent) required to confirm a zigzag pivot."""

_HUNDRED = Decimal("100")


@dataclass(frozen=True, slots=True)
class Pivot:
    """A confirmed zigzag turning point."""

    bar_date: date
    price: Decimal
    kind: str  # "H" | "L"


def zigzag_pivots(
    bars: tuple[OHLCVBar, ...] | list[OHLCVBar],
    threshold_pct: Decimal = DEFAULT_ZIGZAG_THRESHOLD_PCT,
) -> tuple[Pivot, ...]:
    """Return confirmed alternating swing highs/lows via percentage reversal.

    A tracked extreme becomes a pivot only once price reverses ``threshold_pct``
    away from it. The extreme currently being tracked is therefore *not*
    returned: an unreversed extreme is not yet a turning point, and emitting it
    would mean re-labelling history as each new bar arrives.

    Pivots strictly alternate H/L (the tracking direction flips on every
    confirmation) and are separated by at least one bar: the opposite extreme is
    tracked only from bars *after* the confirmed pivot's bar. Without that, a
    single wide-range bar could confirm a reversal against itself and be emitted
    as both a swing high and a swing low on the same date.
    """
    if threshold_pct <= 0:
        raise ValueError("threshold_pct must be positive")
    if len(bars) < 2:
        return ()

    threshold = threshold_pct / _HUNDRED
    pivots: list[Pivot] = []
    direction = 0  # +1 tracking a high, -1 tracking a low, 0 undecided
    hi_bar, lo_bar = bars[0], bars[0]
    hi_idx = lo_idx = 0
    last_pivot_idx = -1  # bar index of the most recent confirmed pivot

    for idx, bar in enumerate(bars):
        # A tracker sitting on (or before) the confirmed pivot's bar is stale:
        # restart it from the current bar to guarantee the separation.
        if direction >= 0 and (hi_idx <= last_pivot_idx or bar.high >= hi_bar.high):
            hi_bar, hi_idx = bar, idx
        if direction <= 0 and (lo_idx <= last_pivot_idx or bar.low <= lo_bar.low):
            lo_bar, lo_idx = bar, idx

        down_move = (hi_bar.high - bar.low) / hi_bar.high
        up_move = (bar.high - lo_bar.low) / lo_bar.low

        reversed_down = down_move >= threshold and direction >= 0
        reversed_up = up_move >= threshold and direction <= 0
        # Both can trigger on the first qualifying bar while undecided; the
        # earlier extreme is the one that actually turned first.
        if reversed_down and (not reversed_up or hi_bar.date <= lo_bar.date):
            pivots.append(Pivot(hi_bar.date, hi_bar.high, "H"))
            direction, last_pivot_idx = -1, hi_idx
        elif reversed_up:
            pivots.append(Pivot(lo_bar.date, lo_bar.low, "L"))
            direction, last_pivot_idx = 1, lo_idx

    return tuple(pivots)
