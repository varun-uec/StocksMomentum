"""Relations between funds: direct–regular pairs, near-duplicates, the regime proxy (method v4).

Each relation is computed once per snapshot from data on or before the as-of date
(doc 21 M4, M7, M8). The regime proxy is an index built from fund NAVs. It is
labelled as a proxy everywhere and is never an official index.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

from wickstreet.analytics.domain.classify import DIRECT, REGULAR
from wickstreet.analytics.domain.metrics import MAX_GAP_DAYS, NO_PAIR, Missing, Value, start_anchor

# ₹10 lakh over 10 years at the observed gap (M4).
WEALTH_AMOUNT = 1_000_000.0
WEALTH_YEARS = 10
NEAR_DUPLICATE = 0.95
# ponytail: candidates come from a fast screen at 0.85 on each fund's own returns; a pair
# whose calendars differ so much that the screen falls below 0.85 is missed.
SCREEN = 0.85
MIN_COMMON_DAYS = 500
MAX_LISTED = 10
PROXY = {
    "category": "Equity Scheme - Large Cap Fund",
    "plan": DIRECT,
    "option": "growth",
    "label": "Proxy: median daily return of large-cap direct growth funds alive each day; "
    "built from fund NAVs, not an official index.",
}
MIN_PROXY_FUNDS = 5
CORRECTION, CRASH = -0.10, -0.20
CORRECTION_KIND, CRASH_KIND, RECOVERY_KIND = "correction", "crash", "recovery"


# ---- direct vs regular


def pairs(keys: Mapping[int, tuple[str, str, str, str]]) -> dict[int, int]:
    """Plan-option id -> its counterpart, for schemes with one direct and one regular plan.

    ``keys`` maps each active fund to (AMC, scheme name, option, plan). A key with more
    than one plan-option on either side is ambiguous and has no pair.
    """
    sides: dict[tuple[str, str, str], dict[str, list[int]]] = defaultdict(
        lambda: {DIRECT: [], REGULAR: []}
    )
    for pid, (amc, scheme, option, plan) in keys.items():
        if amc and scheme:
            sides[(amc, scheme, option)][plan].append(pid)
    found: dict[int, int] = {}
    for side in sides.values():
        if len(side[DIRECT]) == 1 and len(side[REGULAR]) == 1:
            d, r = side[DIRECT][0], side[REGULAR][0]
            found[d], found[r] = r, d
    return found


def _gap(direct: Value, regular: Value) -> Value:
    for value in (direct, regular):
        if isinstance(value, Missing):
            return value
    return float(direct) - float(regular)  # type: ignore[arg-type]


def pair_fields(direct: Mapping[str, Value], regular: Mapping[str, Value]) -> dict[str, Value]:
    """The observed NAV gap between the two plans and its wealth difference (not TER)."""
    values: dict[str, Value] = {
        "dr_gap_1y": _gap(direct["ret_1y"], regular["ret_1y"]),
        "dr_gap_3y": _gap(direct["cagr_3y"], regular["cagr_3y"]),
    }
    gap = values["dr_gap_3y"]
    if isinstance(gap, Missing):
        values["dr_wealth_10y"] = gap
    else:
        d, r = float(direct["cagr_3y"]), float(regular["cagr_3y"])  # type: ignore[arg-type]
        values["dr_wealth_10y"] = WEALTH_AMOUNT * (
            math.pow(1 + d, WEALTH_YEARS) - math.pow(1 + r, WEALTH_YEARS)
        )
    return values


PAIR_FIELDS = ("dr_gap_1y", "dr_gap_3y", "dr_wealth_10y")


def no_pair() -> dict[str, Value]:
    """The pair fields of a fund with no counterpart."""
    return dict.fromkeys(PAIR_FIELDS, Missing("NA", NO_PAIR))


# ---- near-duplicates


@dataclass(frozen=True, slots=True)
class DailyNavs:
    """An active fund's valid NAVs over its 3Y window, from the start anchor, by date ordinal."""

    pid: int
    days: Sequence[int]
    levels: Sequence[float]


def _screen(members: Sequence[DailyNavs]) -> set[tuple[int, int]]:
    """Index pairs whose own daily returns correlate at ``SCREEN`` or more, on shared dates.

    Fast but approximate when two funds publish on different calendars, so it only
    picks candidates for :func:`_exact`.
    """
    days = [np.asarray(m.days[1:]) for m in members]
    columns = {d: k for k, d in enumerate(sorted({int(d) for m in days for d in m}))}
    x = np.full((len(members), len(columns)), np.nan)
    for i, member in enumerate(members):
        levels = np.asarray(member.levels)
        x[i, [columns[int(d)] for d in days[i]]] = levels[1:] / levels[:-1] - 1
    valid = ~np.isnan(x)
    filled = np.where(valid, x, 0.0)
    found: set[tuple[int, int]] = set()
    for i in range(len(members) - 1):
        both = valid[i + 1 :] & valid[i]
        n = both.sum(axis=1).astype(float)
        a = np.where(both, filled[i], 0.0)
        b = np.where(both, filled[i + 1 :], 0.0)
        with np.errstate(invalid="ignore", divide="ignore"):
            cov = (a * b).sum(axis=1) - a.sum(axis=1) * b.sum(axis=1) / n
            var_a = (a * a).sum(axis=1) - a.sum(axis=1) ** 2 / n
            var_b = (b * b).sum(axis=1) - b.sum(axis=1) ** 2 / n
            corr = cov / np.sqrt(var_a * var_b)
        found |= {(i, i + 1 + int(k)) for k in np.flatnonzero(corr >= SCREEN)}
    return found


def _exact(first: DailyNavs, second: DailyNavs) -> tuple[float | None, int]:
    """Pearson correlation of returns between consecutive common dates, as compare reports it."""
    _, i, j = np.intersect1d(first.days, second.days, assume_unique=True, return_indices=True)
    a, b = np.asarray(first.levels)[i], np.asarray(second.levels)[j]
    x, y = a[1:] / a[:-1] - 1, b[1:] / b[:-1] - 1
    n = len(x)
    if n < MIN_COMMON_DAYS:
        return None, n
    dx, dy = x - math.fsum(x) / n, y - math.fsum(y) / n
    sxx, syy = math.fsum(dx * dx), math.fsum(dy * dy)
    if sxx == 0 or syy == 0:
        return None, n
    return math.fsum(dx * dy) / math.sqrt(sxx * syy), n


def near_duplicates(members: Sequence[DailyNavs]) -> dict[int, list[tuple[int, float, int]]]:
    """Per fund: the peers whose returns correlate at ``NEAR_DUPLICATE`` or more.

    A pair is compared on the dates both have a NAV, with returns between consecutive
    common dates (the compare definition), and needs ``MIN_COMMON_DAYS`` returns. Each
    list holds (peer id, correlation, returns compared), highest correlation first.
    """
    found: dict[int, list[tuple[int, float, int]]] = {}
    if len(members) < 2:
        return found
    for i, j in sorted(_screen(members)):
        value, n = _exact(members[i], members[j])
        if value is not None and value >= NEAR_DUPLICATE:
            found.setdefault(members[i].pid, []).append((members[j].pid, value, n))
            found.setdefault(members[j].pid, []).append((members[i].pid, value, n))
    for close in found.values():
        close.sort(key=lambda c: (-c[1], c[0]))
    return found


# ---- regime proxy


def daily_returns(dates: Sequence[int], navs: Sequence[float]) -> list[tuple[int, float]]:
    """(date, return since the previous valid NAV), skipping gaps over ``MAX_GAP_DAYS``."""
    return [
        (dates[k], navs[k] / navs[k - 1] - 1)
        for k in range(1, len(dates))
        if dates[k] - dates[k - 1] <= MAX_GAP_DAYS
    ]


def proxy_index(by_day: Mapping[int, Sequence[float]]) -> list[tuple[int, float]]:
    """A level per day, from 100: the median member return chained over days with 5 funds."""
    level, levels = 100.0, []
    for day in sorted(by_day):
        values = sorted(by_day[day])
        if len(values) < MIN_PROXY_FUNDS:
            continue
        n = len(values)
        median = values[n // 2] if n % 2 else (values[n // 2 - 1] + values[n // 2]) / 2
        level *= 1 + median
        levels.append((day, level))
    return levels


def regimes(levels: Sequence[tuple[int, float]]) -> list[dict[str, Any]]:
    """Falls of 10% or more from a running peak, and the recoveries after them.

    A fall of 20% or more is a ``crash``, otherwise a ``correction``. Its recovery runs
    from the trough to the first level back at the peak; ``ongoing`` when it has not.
    """
    found: list[dict[str, Any]] = []

    def close(peak: int, trough: int, recovery: int | None) -> None:
        depth = levels[trough][1] / levels[peak][1] - 1
        if depth > CORRECTION:
            return
        found.append(
            {
                "kind": CRASH_KIND if depth <= CRASH else CORRECTION_KIND,
                "start": _iso(levels[peak][0]),
                "end": _iso(levels[trough][0]),
                "proxy_return": depth,
            }
        )
        end = len(levels) - 1 if recovery is None else recovery
        found.append(
            {
                "kind": RECOVERY_KIND,
                "start": _iso(levels[trough][0]),
                "end": _iso(levels[end][0]),
                "proxy_return": levels[end][1] / levels[trough][1] - 1,
                "ongoing": recovery is None,
            }
        )

    peak, trough = 0, None
    for k in range(1, len(levels)):
        if levels[k][1] >= levels[peak][1]:
            if trough is not None:
                close(peak, trough, k)
                trough = None
            peak = k
        elif trough is None or levels[k][1] < levels[trough][1]:
            trough = k
    if trough is not None:
        close(peak, trough, None)
    return found


def window_return(dates: Sequence[int], navs: Sequence[float], start: str, end: str) -> Value:
    """The fund's return from the start anchor of ``start`` to that of ``end``."""
    first = start_anchor(dates, date.fromisoformat(start).toordinal())
    if isinstance(first, Missing):
        return first
    last = start_anchor(dates, date.fromisoformat(end).toordinal())
    if isinstance(last, Missing):
        return last
    return navs[last] / navs[first] - 1


def _iso(ordinal: int) -> str:
    return date.fromordinal(ordinal).isoformat()
