"""Daily alerts (FR-22, M15): a condition on one value of a symbol's chart series.

An alert is user data. It reads the same series the chart draws (NFR-1a) and
never feeds a score, gate or rank. It fires once, on the first complete bar
after ``armed_after`` that meets its condition; the owner re-arms it to watch
again. The result depends only on the stored bars, never on when the check ran.

A threshold on a price-scaled source is in the price basis of ``armed_after``,
the latest session when it was set (its factor was then 1). A later split or
bonus rescales every earlier bar, so the threshold is rescaled with them: it is
compared at ``threshold × factor(armed_after)`` in the current schedule. RSI and
ADX do not scale with price.
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

AlertSource = Literal[
    "close", "rsi14", "adx14", "atr14", "macd_line", "macd_signal", "macd_histogram"
]
AlertCondition = Literal[
    "crosses_above", "crosses_below", "above", "below", "enters_zone", "leaves_zone"
]
AlertInterval = Literal["1D", "1W", "1M"]
AlertStatus = Literal["active", "triggered"]


PRICE_SCALED: frozenset[str] = frozenset(
    {"close", "atr14", "macd_line", "macd_signal", "macd_histogram"}
)

DrawingKind = Literal["horizontal", "hline", "rectangle", "trendline", "ray", "extended"]
LineKind = Literal["trendline", "ray", "extended"]
LINE_KINDS: frozenset[str] = frozenset({"trendline", "ray", "extended"})


@dataclass(frozen=True, slots=True)
class DrawingAnchor:
    """An immutable traded-price anchor captured from a saved drawing."""

    date: date
    price: Decimal


@dataclass(frozen=True, slots=True)
class DrawingAlert:
    """A saved drawing snapshot; subsequent drawing edits cannot rewrite a rule."""

    id: str
    kind: DrawingKind
    points: tuple[DrawingAnchor, ...]
    revision: int


@dataclass(frozen=True, slots=True)
class Alert:
    """One stored alert and, once it fired, the bar that fired it."""

    symbol: str
    source: AlertSource
    interval: AlertInterval
    condition: AlertCondition
    threshold: Decimal
    armed_after: date
    status: AlertStatus = "active"
    triggered_on: date | None = None
    trigger_value: Decimal | None = None
    data_version: str | None = None
    seen: bool = False
    created_at: datetime | None = None
    id: int | None = None
    drawing: DrawingAlert | None = None
    revision: int = 1


@dataclass(frozen=True, slots=True)
class SeriesPoint:
    """One bar's value of the alert's source. ``value`` is None during warm-up."""

    date: date
    value: Decimal | None
    partial: bool = False


@dataclass(frozen=True, slots=True)
class Firing:
    """The bar an alert fired on, and its value."""

    date: date
    value: Decimal


def _meets(
    condition: AlertCondition, threshold: Decimal, previous: Decimal | None, value: Decimal
) -> bool:
    if condition == "above":
        return value > threshold
    if condition == "below":
        return value < threshold
    if previous is None:
        return False
    if condition == "crosses_above":
        return previous <= threshold < value
    if condition == "crosses_below":
        return previous >= threshold > value
    return False  # zone rules require both bounds and use first_zone_firing


def first_firing(
    condition: AlertCondition,
    threshold: Decimal,
    armed_after: date,
    points: Sequence[SeriesPoint],
) -> Firing | None:
    """Return the first complete bar after ``armed_after`` that meets the condition.

    ``points`` are in date order. A partial bar (a week or month still
    running) never fires. A bar with no value never fires and never serves as
    the previous bar of a cross. The previous bar may be on or before
    ``armed_after``.
    """
    previous: Decimal | None = None
    for point in points:
        if point.partial:
            break
        if point.value is None:
            previous = None
            continue
        if point.date > armed_after and _meets(condition, threshold, previous, point.value):
            return Firing(date=point.date, value=point.value)
        previous = point.value
    return None


def chart_threshold(source: AlertSource, threshold: Decimal, factor_on_armed: Decimal) -> Decimal:
    """The threshold in the chart's current price basis (see the module note)."""
    return threshold * factor_on_armed if source in PRICE_SCALED else threshold


def first_zone_firing(
    condition: AlertCondition,
    lower: Decimal,
    upper: Decimal,
    armed_after: date,
    points: Sequence[SeriesPoint],
) -> Firing | None:
    """Find the first completed-close entry or exit of an inclusive price zone.

    A close that jumps entirely over the zone does not count as an entry or an
    exit. The rule is independent of the rectangle's visual time extent.
    """
    if lower >= upper or condition not in {"enters_zone", "leaves_zone"}:
        return None
    previous_inside: bool | None = None
    for point in points:
        if point.partial:
            break
        if point.value is None:
            previous_inside = None
            continue
        inside = lower <= point.value <= upper
        if point.date > armed_after and previous_inside is not None:
            entered = not previous_inside and inside
            left = previous_inside and not inside
            if (condition == "enters_zone" and entered) or (condition == "leaves_zone" and left):
                return Firing(point.date, point.value)
        previous_inside = inside
    return None


def line_levels(
    kind: LineKind,
    anchors: tuple[tuple[date, Decimal], tuple[date, Decimal]],
    sessions: Sequence[date],
) -> list[Decimal | None]:
    """The line's value on each session; ``None`` outside the kind's domain.

    ``anchors`` are in the chart's current price basis (each adjusted at its own
    date). A date's index is the number of sessions before it, so the line is
    linear in the session index, as the chart spaces bars (ADR-013 line amendment).
    """
    (date_a, price_a), (date_b, price_b) = anchors
    index_a, index_b = bisect_left(sessions, date_a), bisect_left(sessions, date_b)
    if index_a == index_b:
        raise ValueError("A line needs anchors on two different sessions")
    if kind == "ray" and index_b < index_a:
        raise ValueError("A ray must point forward in time")
    low, high = min(index_a, index_b), max(index_a, index_b)
    slope = (price_b - price_a) / (index_b - index_a)
    levels: list[Decimal | None] = []
    for i in range(len(sessions)):
        inside = kind == "extended" or (kind == "ray" and i >= index_a) or low <= i <= high
        levels.append(price_a + slope * (i - index_a) if inside else None)
    return levels


def first_line_firing(
    condition: AlertCondition,
    armed_after: date,
    points: Sequence[SeriesPoint],
    levels: Sequence[Decimal | None],
) -> Firing | None:
    """The first completed close strictly after ``armed_after`` that crosses the line.

    Each session is compared with the line's value on that session. A session
    without a value or outside the line's domain breaks the crossing.
    """
    if condition not in {"crosses_above", "crosses_below"}:
        return None
    previous: tuple[Decimal, Decimal] | None = None
    for point, level in zip(points, levels, strict=True):
        if point.partial:
            break
        if point.value is None or level is None:
            previous = None
            continue
        if previous is not None and point.date > armed_after:
            close, line = previous
            above = condition == "crosses_above" and close <= line and point.value > level
            below = condition == "crosses_below" and close >= line and point.value < level
            if above or below:
                return Firing(point.date, point.value)
        previous = (point.value, level)
    return None
