"""Elliott Wave labelling of a price series — a chart annotation, not a signal.

Rule set / convention
---------------------
This module applies the three *cardinal rules* of the Wave Principle exactly as
stated in Frost & Prechter, *Elliott Wave Principle: Key to Market Behavior*
(1978), Lesson 2 ("The Cardinal Rules"), which restate R.N. Elliott's original
formulation:

1. Wave 2 never retraces more than 100% of wave 1.
2. Wave 3 is never the shortest of waves 1, 3 and 5.
3. Wave 4 never enters the price territory of wave 1.

Rule 3 is applied in its plain (non-diagonal) form: diagonal triangles, the one
structure in which wave 4 may overlap wave 1, are **not** implemented here, so
no overlap exception is granted. Corrective structures are labelled A-B-C using
the same source's zigzag convention (wave B does not exceed the origin of A).

Guidelines used only for the *projection zone* (Fibonacci relationships from the
same text, Lesson 21 "Ratio Analysis") are guidelines, not rules: they never
accept or reject a count, they only produce a range.

Everything here is pure and deterministic: same bars in, same labels out. No
I/O, no clock, no randomness. This module produces labels and a projected range;
it never produces a buy/sell verdict, a score, or a trade recommendation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from momentum25.domain.entities.market_data import OHLCVBar

DEFAULT_ZIGZAG_THRESHOLD_PCT = Decimal("5")
"""Reversal size (percent) required to confirm a zigzag pivot."""

# Degree names (Frost & Prechter, Lesson 1) inferred from the span of the count
# in trading sessions. A degree cannot be established absolutely from one
# series, so this is a description of the span of the labelled structure, not a
# claim about its place in a larger hierarchy.
_DEGREE_BANDS: tuple[tuple[int, str], ...] = (
    (60, "Minute"),
    (250, "Minor"),
    (750, "Intermediate"),
)
_LARGEST_DEGREE = "Primary"

_ONE = Decimal("1")
_HUNDRED = Decimal("100")


@dataclass(frozen=True, slots=True)
class Pivot:
    """A confirmed zigzag turning point."""

    bar_date: date
    price: Decimal
    kind: str  # "H" | "L"


@dataclass(frozen=True, slots=True)
class WaveLabel:
    """One labelled wave terminal: the pivot at which that wave ended."""

    label: str  # "0" | "1".."5" | "A" | "B" | "C"
    bar_date: date
    price: Decimal


@dataclass(frozen=True, slots=True)
class ProjectionZone:
    """Where the *next* wave would end if a standard Fibonacci ratio holds.

    Always a range, never a point, and always a guideline-derived expectation
    rather than a forecast the platform stands behind.
    """

    low: Decimal
    high: Decimal
    basis: str


@dataclass(frozen=True, slots=True)
class WaveCount:
    """One internally consistent labelling of the pivot sequence."""

    pattern: str  # "impulse" | "correction"
    direction: str  # "up" | "down"
    degree: str
    labels: tuple[WaveLabel, ...]
    current_position: str
    rules_applied: tuple[str, ...]
    # True when the count runs through the most recent confirmed pivot, i.e. it
    # describes the structure now in progress rather than a completed one that
    # later price action has already left behind.
    is_current: bool = True
    projection: ProjectionZone | None = None


@dataclass(frozen=True, slots=True)
class ElliottWaveAnalysis:
    """The full labelling result for one symbol."""

    symbol: str
    as_of: date | None
    threshold_pct: Decimal
    bars_analyzed: int
    pivots: tuple[Pivot, ...]
    primary: WaveCount | None = None
    alternative: WaveCount | None = None
    notes: tuple[str, ...] = field(default_factory=tuple)


# ── Zigzag pivot detection ───────────────────────────────────────────────


def zigzag_pivots(
    bars: tuple[OHLCVBar, ...] | list[OHLCVBar],
    threshold_pct: Decimal = DEFAULT_ZIGZAG_THRESHOLD_PCT,
) -> tuple[Pivot, ...]:
    """Return confirmed alternating swing highs/lows via percentage reversal.

    A tracked extreme becomes a pivot only once price reverses ``threshold_pct``
    away from it. The extreme currently being tracked is therefore *not*
    returned: an unreversed extreme is not yet a turning point, and emitting it
    would mean re-labelling history as each new bar arrives.
    """
    if threshold_pct <= 0:
        raise ValueError("threshold_pct must be positive")
    if len(bars) < 2:
        return ()

    threshold = threshold_pct / _HUNDRED
    pivots: list[Pivot] = []
    direction = 0  # +1 tracking a high, -1 tracking a low, 0 undecided
    hi_bar, lo_bar = bars[0], bars[0]

    for bar in bars:
        if direction >= 0 and bar.high >= hi_bar.high:
            hi_bar = bar
        if direction <= 0 and bar.low <= lo_bar.low:
            lo_bar = bar

        down_move = (hi_bar.high - bar.low) / hi_bar.high
        up_move = (bar.high - lo_bar.low) / lo_bar.low

        if direction == 1:
            if down_move >= threshold:
                pivots.append(Pivot(hi_bar.date, hi_bar.high, "H"))
                direction, lo_bar = -1, bar
        elif direction == -1:
            if up_move >= threshold:
                pivots.append(Pivot(lo_bar.date, lo_bar.low, "L"))
                direction, hi_bar = 1, bar
        else:
            reversed_down = down_move >= threshold
            reversed_up = up_move >= threshold
            # Both can trigger on the first qualifying bar; the earlier extreme
            # is the one that actually turned first.
            if reversed_down and (not reversed_up or hi_bar.date <= lo_bar.date):
                pivots.append(Pivot(hi_bar.date, hi_bar.high, "H"))
                direction, lo_bar = -1, bar
            elif reversed_up:
                pivots.append(Pivot(lo_bar.date, lo_bar.low, "L"))
                direction, hi_bar = 1, bar

    return tuple(pivots)


# ── Wave labelling ───────────────────────────────────────────────────────

_IMPULSE_RULES = (
    "Wave 2 does not retrace beyond the start of wave 1",
    "Wave 3 is not the shortest of waves 1, 3 and 5",
    "Wave 4 does not enter wave 1's price territory (no diagonal exception applied)",
)
_CORRECTION_RULES = ("Wave B does not retrace beyond the start of wave A",)


def _degree(span_sessions: int) -> str:
    for limit, name in _DEGREE_BANDS:
        if span_sessions < limit:
            return name
    return _LARGEST_DEGREE


def _valid_impulse(prices: list[Decimal], up: bool) -> bool:
    """Check the cardinal rules over the terminal prices ``[p0, p1, ...]``.

    ``prices`` holds the origin followed by each labelled wave terminal, so a
    complete impulse is six entries. Partial counts are validated over the rules
    whose waves exist.
    """
    sign = _ONE if up else -_ONE
    p = [sign * x for x in prices]  # normalise so "up" always means increasing

    for i in range(1, len(p)):
        # Alternation must hold: odd waves advance, even waves retrace.
        if i % 2 == 1 and p[i] <= p[i - 1]:
            return False
        if i % 2 == 0 and p[i] >= p[i - 1]:
            return False

    if len(p) > 2 and p[2] <= p[0]:  # rule 1
        return False
    if len(p) > 4 and p[4] <= p[1]:  # rule 3 (no diagonal exception)
        return False
    if len(p) > 5:  # rule 2
        w1, w3, w5 = p[1] - p[0], p[3] - p[2], p[5] - p[4]
        if w3 < w1 and w3 < w5:
            return False
    return True


def _impulse_projection(prices: list[Decimal], up: bool) -> ProjectionZone | None:
    """Fibonacci zone for the wave that follows the last labelled terminal."""
    sign = _ONE if up else -_ONE
    n = len(prices) - 1  # waves already labelled

    def zone(anchor: Decimal, length: Decimal, lo: str, hi: str, basis: str) -> ProjectionZone:
        a = anchor + sign * length * Decimal(lo)
        b = anchor + sign * length * Decimal(hi)
        return ProjectionZone(low=min(a, b), high=max(a, b), basis=basis)

    if n == 1:  # wave 2 retraces wave 1
        w1 = abs(prices[1] - prices[0])
        return zone(prices[1], -w1, "0.5", "0.618", "wave 2: 0.5-0.618 retracement of wave 1")
    if n == 2:  # wave 3 extends wave 1
        w1 = abs(prices[1] - prices[0])
        return zone(prices[2], w1, "1.618", "2.618", "wave 3: 1.618-2.618 extension of wave 1")
    if n == 3:  # wave 4 retraces wave 3
        w3 = abs(prices[3] - prices[2])
        return zone(prices[3], -w3, "0.236", "0.382", "wave 4: 0.236-0.382 retracement of wave 3")
    if n == 4:  # wave 5 projected from the wave 4 terminal
        w1 = abs(prices[1] - prices[0])
        return zone(prices[4], w1, "0.618", "1.0", "wave 5: 0.618-1.0 of wave 1 from wave 4")
    if n == 5:  # impulse complete: the A-B-C correction retraces it
        total = abs(prices[5] - prices[0])
        return zone(
            prices[5], -total, "0.382", "0.618", "correction: 0.382-0.618 retracement of waves 1-5"
        )
    return None


def _correction_projection(prices: list[Decimal], up: bool) -> ProjectionZone | None:
    """Fibonacci zone for the next leg of an A-B-C correction."""
    sign = _ONE if up else -_ONE
    n = len(prices) - 1
    if n == 1:  # wave B retraces wave A
        a = abs(prices[1] - prices[0])
        lo = prices[1] + sign * a * Decimal("0.5")
        hi = prices[1] + sign * a * Decimal("0.786")
        return ProjectionZone(min(lo, hi), max(lo, hi), "wave B: 0.5-0.786 retracement of wave A")
    if n == 2:  # wave C relative to wave A
        a = abs(prices[1] - prices[0])
        lo = prices[2] - sign * a * Decimal("1.0")
        hi = prices[2] - sign * a * Decimal("1.618")
        return ProjectionZone(min(lo, hi), max(lo, hi), "wave C: 1.0-1.618 of wave A from wave B")
    return None


_IMPULSE_LABELS = ("0", "1", "2", "3", "4", "5")
_CORRECTION_LABELS = ("0", "A", "B", "C")


_MIN_WAVES = 2


def _position(in_progress: str, is_current: bool, ends: date) -> str:
    """Describe where the count stands, without overstating a stale structure."""
    if is_current:
        return in_progress
    return (
        f"{in_progress} as of {ends.isoformat()}; later price action does not extend "
        "this count, so no projection is offered"
    )


def _counts_at(
    pivots: tuple[Pivot, ...], start: int, span_sessions: int, last_pivot_date: date
) -> list[WaveCount]:
    """Every valid count anchored at ``pivots[start]``, longest prefix per pattern.

    A structure that breaks a cardinal rule at wave *n* is not discarded
    outright: the labelling is truncated to the longest prefix that satisfies
    every rule, which is what a rule violation actually tells you -- the count
    cannot be extended that far, not that no count exists. Counts shorter than
    ``_MIN_WAVES`` waves are not returned: a single leg is a move, not a
    structure.
    """
    up = pivots[start].kind == "L"
    degree = _degree(span_sessions)
    counts: list[WaveCount] = []
    min_size = _MIN_WAVES + 1

    for size in range(len(_IMPULSE_LABELS), min_size - 1, -1):
        segment = pivots[start : start + size]
        prices = [p.price for p in segment]
        if len(prices) == size and _valid_impulse(prices, up):
            waves = size - 1
            is_current = segment[-1].bar_date == last_pivot_date
            counts.append(
                WaveCount(
                    pattern="impulse",
                    direction="up" if up else "down",
                    degree=degree,
                    labels=tuple(
                        WaveLabel(_IMPULSE_LABELS[i], p.bar_date, p.price)
                        for i, p in enumerate(segment)
                    ),
                    current_position=_position(
                        (
                            f"Wave {waves} complete, wave {waves + 1} in progress"
                            if waves < 5
                            else "Waves 1-5 complete, A-B-C correction expected"
                        ),
                        is_current,
                        segment[-1].bar_date,
                    ),
                    rules_applied=_IMPULSE_RULES,
                    is_current=is_current,
                    projection=_impulse_projection(prices, up) if is_current else None,
                )
            )
            break

    for size in range(len(_CORRECTION_LABELS), min_size - 1, -1):
        segment = pivots[start : start + size]
        prices = [p.price for p in segment]
        if len(prices) == size and _valid_correction(prices, up):
            waves = size - 1
            is_current = segment[-1].bar_date == last_pivot_date
            counts.append(
                WaveCount(
                    pattern="correction",
                    direction="up" if up else "down",
                    degree=degree,
                    labels=tuple(
                        WaveLabel(_CORRECTION_LABELS[i], p.bar_date, p.price)
                        for i, p in enumerate(segment)
                    ),
                    current_position=_position(
                        (
                            f"Wave {_CORRECTION_LABELS[waves]} complete, "
                            f"wave {_CORRECTION_LABELS[waves + 1]} in progress"
                            if waves < 3
                            else "Waves A-B-C complete"
                        ),
                        is_current,
                        segment[-1].bar_date,
                    ),
                    rules_applied=_CORRECTION_RULES,
                    is_current=is_current,
                    projection=_correction_projection(prices, up) if is_current else None,
                )
            )
            break

    return counts


def _valid_correction(prices: list[Decimal], up: bool) -> bool:
    """Zigzag A-B-C: legs alternate and B does not retrace beyond A's origin."""
    sign = _ONE if up else -_ONE
    p = [sign * x for x in prices]
    for i in range(1, len(p)):
        if i % 2 == 1 and p[i] <= p[i - 1]:
            return False
        if i % 2 == 0 and p[i] >= p[i - 1]:
            return False
    return not (len(p) > 2 and p[2] <= p[0])


def label_waves(
    pivots: tuple[Pivot, ...], span_sessions: int
) -> tuple[WaveCount | None, WaveCount | None]:
    """Return ``(primary, alternative)`` counts over ``pivots``.

    The primary count is the structure that reaches the *most recent* confirmed
    pivot — a count that terminated months ago describes history, not the wave
    now in progress — and among those the longest, from the earliest anchor that
    achieves it (the largest structure the visible history justifies). An impulse
    wins a tie against a correction of equal length.

    An alternative is returned **only** when another valid count of
    at least three labelled waves explains the *same* pivot range differently:
    it must start no later than the primary's origin and end at the same final
    pivot. A shorter sub-count nested inside the primary is not an alternative
    reading of the same price action, so it is not offered as one.
    """
    candidates: list[tuple[int, WaveCount]] = []
    for start in range(len(pivots) - 1):
        candidates.extend(
            (start, count)
            for count in _counts_at(pivots, start, span_sessions, pivots[-1].bar_date)
        )
    if not candidates:
        return None, None

    def waves(count: WaveCount) -> int:
        return len(count.labels) - 1

    def rank(item: tuple[int, WaveCount]) -> tuple[int, int, int, int]:
        start, count = item
        return (
            1 if count.is_current else 0,
            waves(count),
            -start,
            1 if count.pattern == "impulse" else 0,
        )

    best = max(candidates, key=rank)
    primary = best[1]

    alternative = next(
        (
            count
            for start, count in sorted(candidates, key=rank, reverse=True)
            if (start, count) != best
            and waves(count) >= 3
            and start <= best[0]
            and count.is_current
        ),
        None,
    )
    return primary, alternative


def analyze_elliott_wave(
    symbol: str,
    bars: tuple[OHLCVBar, ...] | list[OHLCVBar],
    threshold_pct: Decimal = DEFAULT_ZIGZAG_THRESHOLD_PCT,
) -> ElliottWaveAnalysis:
    """Detect pivots and label the wave structure they support."""
    pivots = zigzag_pivots(bars, threshold_pct)
    as_of = bars[-1].date if bars else None
    primary, alternative = label_waves(pivots, len(bars))

    notes: list[str] = []
    if len(pivots) < 2:
        notes.append(
            f"Only {len(pivots)} confirmed pivot(s) at a {threshold_pct}% reversal threshold — "
            "too few to label a wave structure."
        )
    elif primary is None:
        notes.append(
            "No pivot sequence in the visible history satisfies the cardinal rules, "
            "so no count is asserted."
        )
    if primary is not None and not primary.is_current:
        notes.append(
            "No count reaching the latest confirmed pivot satisfies the rules; the labelled "
            "structure ends earlier and no projection is offered."
        )
    if alternative is None and primary is not None:
        notes.append("The pivots support a single valid count; no alternative is asserted.")

    return ElliottWaveAnalysis(
        symbol=symbol,
        as_of=as_of,
        threshold_pct=threshold_pct,
        bars_analyzed=len(bars),
        pivots=pivots,
        primary=primary,
        alternative=alternative,
        notes=tuple(notes),
    )
