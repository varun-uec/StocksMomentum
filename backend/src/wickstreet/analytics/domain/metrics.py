"""Methodology v1: NAV-only metrics of one plan-option (ADR-017 MF-8, MF-11).

``docs/current/mf-metrics.md`` is the method spec. Any change that alters a
computed value, a category or a classification bumps ``METHOD_VERSION``, so a
snapshot never mixes two methods.

Dates are ordinals (``date.toordinal``). A NAV is valid when it is a finite number
above zero; other rows are excluded and counted. Flagged jumps are kept and counted.
"""

from __future__ import annotations

import math
from bisect import bisect_right
from calendar import monthrange
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from functools import cache
from typing import Literal

# v1: the methodology approved on 2026-10-23. v2: v1 with the option rule fixed after
# the real-data spot check (unclaimed-dividend plans, "IDCW Yield", "RetireInvest").
METHOD_VERSION = 2
# The longest gap between two valid NAVs an anchor or a window may span.
MAX_GAP_DAYS = 7
# A fund is active when its last valid NAV is this close to the as-of date.
ACTIVE_DAYS = 7
YEAR_DAYS = 365.25
ANNUALISE_VOL = math.sqrt(252)
MIN_SINCE_DAYS = 365
JUMP = "nav_jump"

NO_NAV = "no_nav"
NO_RECENT_NAV = "no_recent_nav"
HISTORY_TOO_SHORT = "history_too_short"
GAP_AT_START = "gap_at_start"
GAP_IN_WINDOW = "gap_in_window"
REASONS = frozenset({NO_NAV, NO_RECENT_NAV, HISTORY_TOO_SHORT, GAP_AT_START, GAP_IN_WINDOW})


@dataclass(frozen=True, slots=True)
class Missing:
    """No value: not available (``NA``) or not meaningful (``NM``), and why."""

    state: Literal["NA", "NM"]
    reason: str


Value = float | int | bool | str | Missing

# (field, calendar months back from the as-of date, annualised)
TRAILING = (
    ("ret_1m", 1, False),
    ("ret_3m", 3, False),
    ("ret_6m", 6, False),
    ("ret_1y", 12, False),
    ("cagr_3y", 36, True),
    ("cagr_5y", 60, True),
    ("cagr_10y", 120, True),
)
ROLLING = (("rolling_1y", 12), ("rolling_3y", 36), ("rolling_5y", 60))
ROLLING_STATS = ("count", "mean", "median", "min", "max", "positive_share")
VOLATILITY = (("vol_1y", 12), ("vol_3y", 36))
DRAWDOWN = (("mdd_1y", 12), ("mdd_3y", 36))
SINCE = ("since_start", "ret_since", "cagr_since", "mdd_since")
LATEST = ("active", "nav", "last_nav_date", "excluded_navs", "jump_flags")
METRIC_FIELDS = (
    *LATEST,
    *(name for name, _, _ in TRAILING),
    *SINCE,
    *(name for name, _ in VOLATILITY),
    *(name for name, _ in DRAWDOWN),
    *(f"{name}_{stat}" for name, _ in ROLLING for stat in ROLLING_STATS),
)


@dataclass(frozen=True, slots=True)
class FundMetrics:
    """Every metric of one fund, and the start date each trailing return used."""

    values: dict[str, Value]
    anchors: dict[str, str]


@cache
def months_back(ordinal: int, months: int) -> int:
    """The date ``months`` calendar months earlier, its day clamped to the month end."""
    day = date.fromordinal(ordinal)
    year, month = divmod(day.year * 12 + day.month - 1 - months, 12)
    month += 1
    return date(year, month, min(day.day, monthrange(year, month)[1])).toordinal()


def _iso(ordinal: int) -> str:
    return date.fromordinal(ordinal).isoformat()


def _cagr(start: float, end: float, days: int) -> float:
    return math.pow(end / start, YEAR_DAYS / days) - 1


def _start(dates: Sequence[int], target: int) -> int | Missing:
    """The last valid NAV on or before ``target``, at most ``MAX_GAP_DAYS`` before it."""
    index = bisect_right(dates, target) - 1
    if index < 0:
        return Missing("NA", HISTORY_TOO_SHORT)
    if target - dates[index] > MAX_GAP_DAYS:
        return Missing("NA", GAP_AT_START)
    return index


def _has_gap(dates: Sequence[int], start: int, end: int) -> bool:
    return any(dates[k] - dates[k - 1] > MAX_GAP_DAYS for k in range(start + 1, end + 1))


def volatility(dates: Sequence[int], navs: Sequence[float], start: int, end: int) -> Value:
    """Sample standard deviation of returns between consecutive NAVs, times √252."""
    if end - start < 2:
        return Missing("NA", HISTORY_TOO_SHORT)
    if _has_gap(dates, start, end):
        return Missing("NM", GAP_IN_WINDOW)
    returns = [navs[k] / navs[k - 1] - 1 for k in range(start + 1, end + 1)]
    mean = math.fsum(returns) / len(returns)
    variance = math.fsum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return math.sqrt(variance) * ANNUALISE_VOL


def drawdown(dates: Sequence[int], navs: Sequence[float], start: int, end: int) -> Value:
    """The largest fall from a running peak, as a fraction (always <= 0)."""
    if _has_gap(dates, start, end):
        return Missing("NM", GAP_IN_WINDOW)
    peak = navs[start]
    worst = 0.0
    for k in range(start + 1, end + 1):
        nav = navs[k]
        if nav > peak:
            peak = nav
        elif nav / peak - 1 < worst:
            worst = nav / peak - 1
    return worst


def rolling(dates: Sequence[int], navs: Sequence[float], months: int) -> dict[str, Value]:
    """Summary of the annualised return over every ``months`` window in the history.

    One point per valid date that has a valid start anchor. Targets only move
    forward, so the anchor index does too: one pass per window.
    """
    points: list[float] = []
    anchor = 0
    for j, day in enumerate(dates):
        target = months_back(day, months)
        if target < dates[0]:
            continue
        while dates[anchor + 1] <= target:
            anchor += 1
        if target - dates[anchor] > MAX_GAP_DAYS:
            continue
        points.append(_cagr(navs[anchor], navs[j], day - dates[anchor]))
    if not points:
        missing = Missing("NA", HISTORY_TOO_SHORT)
        empty: dict[str, Value] = {"count": 0}
        return empty | dict.fromkeys(ROLLING_STATS[1:], missing)
    points.sort()
    n = len(points)
    middle = n // 2
    median = points[middle] if n % 2 else (points[middle - 1] + points[middle]) / 2
    return {
        "count": n,
        "mean": math.fsum(points) / n,
        "median": median,
        "min": points[0],
        "max": points[-1],
        "positive_share": sum(1 for p in points if p > 0) / n,
    }


def compute(points: Sequence[tuple[int, float | None, str | None]], as_of: int) -> FundMetrics:
    """Every v1 metric of one fund at ``as_of``, the latest NAV date in the store."""
    dates: list[int] = []
    navs: list[float] = []
    excluded = jumps = 0
    for day, nav, anomaly in points:
        if anomaly == JUMP:
            jumps += 1
        if nav is None or not math.isfinite(nav) or nav <= 0:
            excluded += 1
            continue
        dates.append(day)
        navs.append(nav)
    values: dict[str, Value] = {"excluded_navs": excluded, "jump_flags": jumps}
    anchors: dict[str, str] = {}
    if not dates:
        missing = Missing("NA", NO_NAV)
        values |= {name: missing for name in METRIC_FIELDS if name not in values}
        values["active"] = False
        return FundMetrics(values, anchors)

    end = len(dates) - 1
    active = as_of - dates[end] <= ACTIVE_DAYS
    span = dates[end] - dates[0]
    values |= {
        "active": active,
        "nav": navs[end],
        "last_nav_date": _iso(dates[end]),
        "since_start": _iso(dates[0]),
        "ret_since": navs[end] / navs[0] - 1,
        "cagr_since": (
            _cagr(navs[0], navs[end], span)
            if span >= MIN_SINCE_DAYS
            else Missing("NA", HISTORY_TOO_SHORT)
        ),
        "mdd_since": drawdown(dates, navs, 0, end),
    }
    starts: dict[int, int | Missing] = {}
    for months in {m for _, m, _ in TRAILING}:
        starts[months] = (
            _start(dates, months_back(as_of, months)) if active else Missing("NA", NO_RECENT_NAV)
        )
    for name, months, annualised in TRAILING:
        start = starts[months]
        if isinstance(start, Missing):
            values[name] = start
            continue
        anchors[name] = _iso(dates[start])
        values[name] = (
            _cagr(navs[start], navs[end], dates[end] - dates[start])
            if annualised
            else navs[end] / navs[start] - 1
        )
    for windows, measure in ((VOLATILITY, volatility), (DRAWDOWN, drawdown)):
        for name, months in windows:
            start = starts[months]
            values[name] = start if isinstance(start, Missing) else measure(dates, navs, start, end)
    for name, months in ROLLING:
        for stat, value in rolling(dates, navs, months).items():
            values[f"{name}_{stat}"] = value
    return FundMetrics(values, anchors)


def rebase(
    points: Sequence[tuple[int, float | None, str | None]], start: int
) -> list[tuple[str, float]]:
    """Valid NAVs from ``start`` on, scaled to 100 at the first of them."""
    valid = [
        (d, n) for d, n, _ in points if d >= start and n is not None and math.isfinite(n) and n > 0
    ]
    if not valid:
        return []
    base = valid[0][1]
    return [(_iso(d), n / base * 100) for d, n in valid]
