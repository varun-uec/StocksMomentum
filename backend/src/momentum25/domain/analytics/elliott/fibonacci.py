"""Fibonacci ratio analysis between labelled turning points — price *and* time.

Source: Frost & Prechter, *Elliott Wave Principle* (1978), Lesson 21 ("Ratio
Analysis"), which gives both the price relationships between waves and the
Fibonacci time relationships between their turning points.

Everything here is a **guideline**. A ratio that misses its canonical value never
rejects a count; it lowers the count's measured adherence, which the ranking
reports transparently. The one range this module emits — the projection zone —
is a range by construction, is described as guideline-derived, and is consumed
only by the Elliott Wave research surface. It is never an input to the
Momentum25 score, ranking, gates, Trend Template or stop-loss, and it is never a
target price or a profit projection.

Time analysis measures *elapsed sessions between confirmed turning points*. It
deliberately projects no future turning date: a projected date is a forecast, and
this surface makes none.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

_ONE = Decimal("1")
_ZERO = Decimal("0")

CANONICAL_RATIOS: tuple[Decimal, ...] = tuple(
    Decimal(r)
    for r in ("0.236", "0.382", "0.5", "0.618", "0.786", "1.0", "1.272", "1.618", "2.618")
)
"""The Fibonacci-derived ratios Lesson 21 works in, price and time alike."""

_QUANTUM = Decimal("0.001")
"""Egress precision for published ratios (ADR-009): rounded once, at
construction, so the number shown is the number that was scored."""

_PRICE_QUANTUM = Decimal("0.01")
"""Egress precision for the projection zone's bounds, which are prices."""

PRICE = "price"
TIME = "time"


@dataclass(frozen=True, slots=True)
class FibonacciRelationship:
    """One measured relationship between two waves of the same count."""

    kind: str  # PRICE | TIME
    name: str  # e.g. "wave 3 / wave 1"
    observed: Decimal
    nearest: Decimal
    proximity: Decimal  # 0-1; 1.0 is an exact hit on `nearest`
    detail: str


@dataclass(frozen=True, slots=True)
class ProjectionZone:
    """Where the *next* wave would end if a standard Fibonacci ratio held.

    Always a range, never a point, and always a guideline-derived expectation
    rather than a forecast the platform stands behind. Consumed only by the
    Elliott Wave research surface; the Momentum25 score, rank, gates and
    stop-loss never read it.
    """

    low: Decimal
    high: Decimal
    basis: str


# Which leg pairs are worth measuring, per pattern. Index pairs are into the
# leg list (leg 0 is the first wave). Lesson 21 names these explicitly for
# impulses and zigzags; the triangle and combination pairs are the same
# leg-to-leg comparison applied to those structures' components.
_RATIO_PAIRS: dict[str, tuple[tuple[str, int, int], ...]] = {
    "impulse": (
        ("wave 2 / wave 1", 1, 0),
        ("wave 3 / wave 1", 2, 0),
        ("wave 4 / wave 3", 3, 2),
        ("wave 5 / wave 1", 4, 0),
        ("wave 5 / wave 3", 4, 2),
    ),
    "diagonal": (
        ("wave 2 / wave 1", 1, 0),
        ("wave 3 / wave 1", 2, 0),
        ("wave 4 / wave 3", 3, 2),
        ("wave 5 / wave 3", 4, 2),
    ),
    "zigzag": (("wave B / wave A", 1, 0), ("wave C / wave A", 2, 0)),
    "flat": (("wave B / wave A", 1, 0), ("wave C / wave A", 2, 0)),
    "triangle": (
        ("wave C / wave A", 2, 0),
        ("wave D / wave B", 3, 1),
        ("wave E / wave C", 4, 2),
    ),
    "double three": (("wave Y / wave W", 2, 0),),
    "triple three": (("wave Y / wave W", 2, 0), ("wave Z / wave Y", 4, 2)),
}


def nearest_ratio(observed: Decimal) -> tuple[Decimal, Decimal]:
    """Return ``(nearest canonical ratio, proximity)`` for ``observed``.

    Proximity is ``1 - |observed - nearest| / nearest``, floored at zero: 1.0 is
    an exact hit, 0.0 means the observation is at least as far from the ratio as
    the ratio is from zero.
    """
    nearest = min(CANONICAL_RATIOS, key=lambda r: (abs(observed - r), r))
    proximity = (_ONE - abs(observed - nearest) / nearest).quantize(_QUANTUM)
    return nearest, max(proximity, _ZERO)


def _relationship(
    kind: str, name: str, numerator: Decimal, denominator: Decimal, unit: str
) -> FibonacciRelationship | None:
    if denominator == _ZERO:
        return None
    observed = (abs(numerator) / abs(denominator)).quantize(_QUANTUM)
    nearest, proximity = nearest_ratio(observed)
    return FibonacciRelationship(
        kind=kind,
        name=name,
        observed=observed,
        nearest=nearest,
        proximity=proximity,
        detail=f"{observed:.3f} observed ({unit}); nearest Fibonacci ratio {nearest}",
    )


def price_relationships(pattern: str, prices: list[Decimal]) -> tuple[FibonacciRelationship, ...]:
    """Measured price ratios between the labelled waves of one count."""
    legs = [b - a for a, b in zip(prices, prices[1:], strict=False)]
    found = []
    for name, i, j in _RATIO_PAIRS.get(pattern, ()):
        if i < len(legs) and j < len(legs):
            rel = _relationship(PRICE, name, legs[i], legs[j], "price")
            if rel is not None:
                found.append(rel)
    return tuple(found)


def time_relationships(
    pattern: str, dates: list[date], sessions: dict[date, int]
) -> tuple[FibonacciRelationship, ...]:
    """Measured *duration* ratios between the same waves, in trading sessions.

    Durations come from the session index of each turning point, so a leg that
    straddles holidays is measured in bars actually traded rather than calendar
    days. A turning point outside ``sessions`` (possible only if a caller mixes
    label sets) yields no relationship rather than a guessed one.
    """
    try:
        indexes = [sessions[d] for d in dates]
    except KeyError:
        return ()
    durations = [Decimal(b - a) for a, b in zip(indexes, indexes[1:], strict=False)]
    found = []
    for name, i, j in _RATIO_PAIRS.get(pattern, ()):
        if i < len(durations) and j < len(durations):
            rel = _relationship(TIME, f"{name} (duration)", durations[i], durations[j], "sessions")
            if rel is not None:
                found.append(rel)
    return tuple(found)


def adherence(relationships: tuple[FibonacciRelationship, ...]) -> Decimal | None:
    """Mean proximity across ``relationships``; ``None`` when none were measurable."""
    if not relationships:
        return None
    return sum((r.proximity for r in relationships), _ZERO) / Decimal(len(relationships))


# ── projection zone ──────────────────────────────────────────────────────


def _zone(anchor: Decimal, length: Decimal, lo: str, hi: str, basis: str) -> ProjectionZone:
    a = (anchor + length * Decimal(lo)).quantize(_PRICE_QUANTUM)
    b = (anchor + length * Decimal(hi)).quantize(_PRICE_QUANTUM)
    return ProjectionZone(low=min(a, b), high=max(a, b), basis=basis)


def projection(
    pattern: str, prices: list[Decimal], up: bool, variant: str | None = None
) -> ProjectionZone | None:
    """Guideline range for the wave that would follow the last labelled terminal.

    ``prices`` are the raw (un-normalised) terminals. Returns ``None`` where the
    text gives no standard proportion for the next leg — an absent range is more
    honest than an invented one.
    """
    sign = _ONE if up else -_ONE
    n = len(prices) - 1  # waves already labelled

    if pattern in ("impulse", "diagonal"):
        if n == 1:
            w1 = abs(prices[1] - prices[0])
            return _zone(
                prices[1], -sign * w1, "0.5", "0.618", "wave 2: 0.5-0.618 retracement of wave 1"
            )
        if n == 2:
            w1 = abs(prices[1] - prices[0])
            return _zone(
                prices[2], sign * w1, "1.618", "2.618", "wave 3: 1.618-2.618 extension of wave 1"
            )
        if n == 3:
            w3 = abs(prices[3] - prices[2])
            return _zone(
                prices[3], -sign * w3, "0.236", "0.382", "wave 4: 0.236-0.382 retracement of wave 3"
            )
        if n == 4:
            w1 = abs(prices[1] - prices[0])
            return _zone(
                prices[4], sign * w1, "0.618", "1.0", "wave 5: 0.618-1.0 of wave 1 from wave 4"
            )
        if n == 5:
            total = abs(prices[5] - prices[0])
            return _zone(
                prices[5],
                -sign * total,
                "0.382",
                "0.618",
                "correction: 0.382-0.618 retracement of waves 1-5",
            )
        return None

    if pattern in ("zigzag", "flat"):
        a = abs(prices[1] - prices[0])
        if n == 1:
            lo, hi = ("0.5", "0.786") if pattern == "zigzag" else ("0.9", "1.382")
            return _zone(
                prices[1],
                -sign * a,
                lo,
                hi,
                f"wave B: {lo}-{hi} retracement of wave A",
            )
        if n == 2:
            return _zone(
                prices[2], sign * a, "1.0", "1.618", "wave C: 1.0-1.618 of wave A from wave B"
            )
        return None

    # The 0.618-0.786 wave-E proportion is the *contracting* triangle's; an
    # expanding triangle's legs grow, and the text gives it no equivalent, so no
    # range is offered rather than one borrowed from the wrong form.
    if pattern == "triangle" and n == 4 and variant == "contracting":
        c = abs(prices[3] - prices[2])
        return _zone(
            prices[4],
            sign * c,
            "0.618",
            "0.786",
            "wave E: 0.618-0.786 of wave C, the contracting-triangle proportion",
        )

    return None
