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

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

AlertSource = Literal[
    "close", "rsi14", "adx14", "atr14", "macd_line", "macd_signal", "macd_histogram"
]
AlertCondition = Literal["crosses_above", "crosses_below", "above", "below"]
AlertInterval = Literal["1D", "1W", "1M"]
AlertStatus = Literal["active", "triggered"]


PRICE_SCALED: frozenset[str] = frozenset(
    {"close", "atr14", "macd_line", "macd_signal", "macd_histogram"}
)


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
    return previous >= threshold > value


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
