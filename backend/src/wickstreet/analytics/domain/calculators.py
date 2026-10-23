"""Investment simulations over a fund's real NAV history (doc 03 §2.6, doc 20 §3).

Rules (``CALCULATOR_VERSION``):

- An instalment is scheduled each month on ``day`` (clamped to the month end) and
  trades at the first valid NAV on or after that date, until ``end``.
- A purchase pays stamp duty of 0.005% from 2020-07-01: units = amount × (1 − duty) ÷ NAV.
- Redemptions take units first in, first out; their gains feed :mod:`tax`.
- The final value uses the last valid NAV on or before ``end``.
- XIRR solves for the annual rate that sets the net present value of the cash flows
  to zero, by bisection; ``None`` when no rate in (−99.99%, 10,000%) does.
"""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from calendar import monthrange
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from wickstreet.analytics.domain.metrics import valid_series
from wickstreet.analytics.domain.tax import Sale

CALCULATOR_VERSION = 1
STAMP_DUTY = 0.00005
STAMP_DUTY_FROM = date(2020, 7, 1).toordinal()
_XIRR_LOW, _XIRR_HIGH, _XIRR_STEPS = -0.9999, 100.0, 200

Points = Sequence[tuple[int, float | None, str | None]]


class SimulationError(ValueError):
    """The inputs cannot be simulated over this fund's history."""


@dataclass(frozen=True, slots=True)
class Series:
    """The valid NAVs of one fund."""

    dates: list[int]
    navs: list[float]

    @classmethod
    def of(cls, points: Points) -> Series:
        """Keep the valid NAVs."""
        dates, navs, _, _ = valid_series(points)
        return cls(dates, navs)

    def on_or_after(self, day: int) -> int | None:
        """Index of the first NAV on or after ``day``."""
        index = bisect_left(self.dates, day)
        return index if index < len(self.dates) else None

    def on_or_before(self, day: int) -> int | None:
        """Index of the last NAV on or before ``day``."""
        index = bisect_right(self.dates, day) - 1
        return index if index >= 0 else None


@dataclass(slots=True)
class Holding:
    """Purchase lots of one fund: (bought, units, cost per unit)."""

    lots: list[list[float]] = field(default_factory=list)

    @property
    def units(self) -> float:
        """Units held."""
        return math.fsum(lot[1] for lot in self.lots)

    def buy(self, day: int, amount: float, nav: float) -> float:
        """Buy for ``amount``; returns the units bought."""
        duty = STAMP_DUTY if day >= STAMP_DUTY_FROM else 0.0
        units = amount * (1 - duty) / nav
        self.lots.append([float(day), units, amount / units])
        return units

    def sell(self, day: int, units: float, nav: float) -> list[Sale]:
        """Redeem ``units`` first in, first out."""
        sales: list[Sale] = []
        left = units
        while left > 1e-12 and self.lots:
            lot = self.lots[0]
            taken = min(lot[1], left)
            sales.append(Sale(int(lot[0]), day, taken, taken * lot[2], taken * nav))
            lot[1] -= taken
            left -= taken
            if lot[1] <= 1e-12:
                self.lots.pop(0)
        return sales


def schedule(start: date, end: date, day: int) -> list[int]:
    """Monthly dates on ``day`` (clamped to the month end) from ``start`` to ``end``."""
    if not 1 <= day <= 31:
        raise SimulationError("day is 1 to 31")
    found: list[int] = []
    year, month = start.year, start.month
    while True:
        scheduled = date(year, month, min(day, monthrange(year, month)[1]))
        if scheduled > end:
            return found
        if scheduled >= start:
            found.append(scheduled.toordinal())
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)


def xirr(flows: Sequence[tuple[int, float]]) -> float | None:
    """Annual rate with zero net present value; flows are (date, amount), money in negative."""
    if not flows or not any(a < 0 for _, a in flows) or not any(a > 0 for _, a in flows):
        return None
    first = flows[0][0]

    def npv(rate: float) -> float:
        return math.fsum(a / (1 + rate) ** ((d - first) / 365) for d, a in flows)

    low, high = _XIRR_LOW, _XIRR_HIGH
    f_low, f_high = npv(low), npv(high)
    if f_low * f_high > 0:
        return None
    for _ in range(_XIRR_STEPS):
        middle = (low + high) / 2
        f_middle = npv(middle)
        if f_low * f_middle <= 0:
            high = middle
        else:
            low, f_low = middle, f_middle
    return (low + high) / 2


def _redeem_all(holding: Holding, series: Series, valued: int) -> list[Sale]:
    """The sales of redeeming every unit at ``valued``, leaving ``holding`` unchanged."""
    copy = Holding([lot[:] for lot in holding.lots])
    return copy.sell(series.dates[valued], copy.units, series.navs[valued])


def _iso(ordinal: int) -> str:
    return date.fromordinal(ordinal).isoformat()


def _valuation(series: Series, end: date) -> int:
    index = series.on_or_before(end.toordinal())
    if index is None:
        raise SimulationError("no NAV on or before the end date")
    return index


@dataclass(frozen=True, slots=True)
class Outcome:
    """A simulation's result.

    ``sales`` are the redemptions the tax estimate covers: the actual ones for SWP
    and STP, and every remaining unit on the valuation date for SIP and lump sum.
    """

    summary: dict[str, Any]
    timeline: list[dict[str, Any]]
    sales: list[Sale]


def _close(
    flows: list[tuple[int, float]],
    holding_value: float,
    valued: int,
    invested: float,
    withdrawn: float,
) -> dict[str, Any]:
    flows = [*flows, (valued, holding_value)]
    return {
        "invested": invested,
        "withdrawn": withdrawn,
        "value": holding_value,
        "gain": holding_value + withdrawn - invested,
        "xirr": xirr(sorted(flows)),
        "valued_on": _iso(valued),
        "calculator_version": CALCULATOR_VERSION,
    }


def sip(
    points: Points, amount: float, day: int, start: date, end: date, step_up: float = 0.0
) -> Outcome:
    """Buy ``amount`` each month; ``step_up`` raises the amount each 12 instalments."""
    if amount <= 0 or step_up < 0:
        raise SimulationError("amount must be positive and step-up not negative")
    series, holding = Series.of(points), Holding()
    flows: list[tuple[int, float]] = []
    timeline: list[dict[str, Any]] = []
    invested = 0.0
    for n, scheduled in enumerate(schedule(start, end, day)):
        index = series.on_or_after(scheduled)
        if index is None or series.dates[index] > end.toordinal():
            break
        paid = amount * (1 + step_up) ** (n // 12)
        traded = series.dates[index]
        holding.buy(traded, paid, series.navs[index])
        invested += paid
        flows.append((traded, -paid))
        timeline.append(
            {
                "date": _iso(traded),
                "invested": invested,
                "value": holding.units * series.navs[index],
            }
        )
    if not flows:
        raise SimulationError("no instalment falls within the fund's NAV history")
    valued = _valuation(series, end)
    value = holding.units * series.navs[valued]
    summary = _close(flows, value, series.dates[valued], invested, 0.0) | {
        "instalments": len(flows),
        "units": holding.units,
    }
    return Outcome(summary, timeline, _redeem_all(holding, series, valued))


def lumpsum(points: Points, amount: float, start: date, end: date) -> Outcome:
    """Buy once at the first NAV on or after ``start``."""
    if amount <= 0:
        raise SimulationError("amount must be positive")
    series, holding = Series.of(points), Holding()
    index = series.on_or_after(start.toordinal())
    if index is None or series.dates[index] > end.toordinal():
        raise SimulationError("no NAV between the start and end dates")
    holding.buy(series.dates[index], amount, series.navs[index])
    valued = _valuation(series, end)
    value = holding.units * series.navs[valued]
    summary = _close([(series.dates[index], -amount)], value, series.dates[valued], amount, 0.0) | {
        "units": holding.units,
        "bought_on": _iso(series.dates[index]),
    }
    return Outcome(summary, [], _redeem_all(holding, series, valued))


def swp(
    points: Points, amount: float, withdrawal: float, day: int, start: date, end: date
) -> Outcome:
    """Invest ``amount`` at ``start``, then redeem ``withdrawal`` each month while units last."""
    if amount <= 0 or withdrawal <= 0:
        raise SimulationError("amounts must be positive")
    series, holding = Series.of(points), Holding()
    first = series.on_or_after(start.toordinal())
    if first is None or series.dates[first] > end.toordinal():
        raise SimulationError("no NAV between the start and end dates")
    holding.buy(series.dates[first], amount, series.navs[first])
    flows: list[tuple[int, float]] = [(series.dates[first], -amount)]
    sales: list[Sale] = []
    timeline: list[dict[str, Any]] = []
    withdrawn = 0.0
    for scheduled in schedule(start, end, day):
        index = series.on_or_after(scheduled)
        if index is None or series.dates[index] > end.toordinal() or index <= first:
            continue
        nav, traded = series.navs[index], series.dates[index]
        units = min(withdrawal / nav, holding.units)
        if units <= 1e-12:
            break
        sales += holding.sell(traded, units, nav)
        withdrawn += units * nav
        flows.append((traded, units * nav))
        timeline.append(
            {"date": _iso(traded), "withdrawn": withdrawn, "value": holding.units * nav}
        )
    valued = _valuation(series, end)
    value = holding.units * series.navs[valued]
    summary = _close(flows, value, series.dates[valued], amount, withdrawn) | {
        "withdrawals": len(flows) - 1,
        "units": holding.units,
    }
    return Outcome(summary, timeline, sales)


def stp(
    source_points: Points,
    target_points: Points,
    amount: float,
    transfer: float,
    day: int,
    start: date,
    end: date,
) -> Outcome:
    """Invest ``amount`` in the source, then move ``transfer`` to the target each month.

    A transfer trades on the first date on or after its scheduled day on which both
    funds have a NAV.
    """
    if amount <= 0 or transfer <= 0:
        raise SimulationError("amounts must be positive")
    source, target = Series.of(source_points), Series.of(target_points)
    held, moved = Holding(), Holding()
    first = source.on_or_after(start.toordinal())
    if first is None or source.dates[first] > end.toordinal():
        raise SimulationError("no source NAV between the start and end dates")
    held.buy(source.dates[first], amount, source.navs[first])
    target_navs = dict(zip(target.dates, target.navs, strict=True))
    sales: list[Sale] = []
    timeline: list[dict[str, Any]] = []
    transferred = 0.0
    for scheduled in schedule(start, end, day):
        index = source.on_or_after(scheduled)
        while (
            index is not None
            and index < len(source.dates)
            and source.dates[index] not in target_navs
        ):
            index += 1
        if index is None or index >= len(source.dates) or source.dates[index] > end.toordinal():
            continue
        if index <= first:
            continue
        nav, traded = source.navs[index], source.dates[index]
        units = min(transfer / nav, held.units)
        if units <= 1e-12:
            break
        sales += held.sell(traded, units, nav)
        proceeds = units * nav
        moved.buy(traded, proceeds, target_navs[traded])
        transferred += proceeds
        timeline.append(
            {
                "date": _iso(traded),
                "transferred": transferred,
                "source_value": held.units * nav,
                "target_value": moved.units * target_navs[traded],
            }
        )
    source_end, target_end = _valuation(source, end), _valuation(target, end)
    value = held.units * source.navs[source_end] + moved.units * target.navs[target_end]
    valued = min(source.dates[source_end], target.dates[target_end])
    summary = _close([(source.dates[first], -amount)], value, valued, amount, 0.0) | {
        "transfers": len(timeline),
        "source_value": held.units * source.navs[source_end],
        "target_value": moved.units * target.navs[target_end],
    }
    return Outcome(summary, timeline, sales)
