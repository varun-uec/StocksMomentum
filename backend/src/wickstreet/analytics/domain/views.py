"""Per-fund views computed on request from one series (doc 20 §3).

They use the same valid-NAV and anchor rules as the snapshot metrics, so a chart
and its figures agree. A partial period is labelled, never silently mixed in.
"""

from __future__ import annotations

import math
from calendar import monthrange
from collections.abc import Sequence
from datetime import date
from typing import Any

from wickstreet.analytics.domain import calculators
from wickstreet.analytics.domain.metrics import (
    Missing,
    nearest_rank,
    start_anchor,
    valid_series,
    window_points,
    year_returns,
)

Points = Sequence[tuple[int, float | None, str | None]]
MIN_OBSERVATIONS = 30


def _iso(ordinal: int) -> str:
    return date.fromordinal(ordinal).isoformat()


def _label(year: int, end_month: int) -> str:
    return str(year) if end_month == 12 else f"FY{year - 1}-{year % 100:02d}"


def _year_of(ordinal: int, end_month: int) -> int:
    day = date.fromordinal(ordinal)
    return day.year if end_month == 12 or day.month <= end_month else day.year + 1


def _years(dates: list[int], navs: list[float], as_of: int, end_month: int) -> list[dict[str, Any]]:
    complete = year_returns(dates, navs, as_of, end_month)
    rows = [{"period": _label(y, end_month), "return": r, "partial": False} for y, r in complete]
    first = _year_of(dates[0], end_month)
    first_end = start_anchor(
        dates, date(first, end_month, monthrange(first, end_month)[1]).toordinal()
    )
    if not isinstance(first_end, Missing) and first_end > 0:
        rows.insert(
            0,
            {
                "period": _label(first, end_month),
                "return": navs[first_end] / navs[0] - 1,
                "partial": True,
            },
        )
    last = _year_of(dates[-1], end_month)
    previous_end = start_anchor(
        dates, date(last - 1, end_month, monthrange(last - 1, end_month)[1]).toordinal()
    )
    closed = any(year == last for year, _ in complete)
    if not closed and not isinstance(previous_end, Missing) and previous_end < len(dates) - 1:
        rows.append(
            {
                "period": _label(last, end_month),
                "return": navs[-1] / navs[previous_end] - 1,
                "partial": True,
            }
        )
    if not rows and len(dates) > 1:
        rows.append(
            {"period": _label(last, end_month), "return": navs[-1] / navs[0] - 1, "partial": True}
        )
    return rows


def _months(dates: list[int], navs: list[float]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    first, last = date.fromordinal(dates[0]), date.fromordinal(dates[-1])
    previous: int | None = None
    key = first.year * 12 + first.month - 1
    while key <= last.year * 12 + last.month - 1:
        year, month = divmod(key, 12)
        index = start_anchor(
            dates, date(year, month + 1, monthrange(year, month + 1)[1]).toordinal()
        )
        if isinstance(index, Missing):
            previous = None
        else:
            if previous is not None and index != previous:
                found.append(
                    {"year": year, "month": month + 1, "return": navs[index] / navs[previous] - 1}
                )
            previous = index
        key += 1
    return found


def annual(points: Points, as_of: int) -> dict[str, list[dict[str, Any]]]:
    """Calendar and financial years (partial ends labelled) and month-end to month-end returns."""
    dates, navs, _, _ = valid_series(points)
    if not dates:
        return {"calendar": [], "financial": [], "monthly": []}
    return {
        "calendar": _years(dates, navs, as_of, 12),
        "financial": _years(dates, navs, as_of, 3),
        "monthly": _months(dates, navs),
    }


def rolling_series(points: Points, months: int) -> list[tuple[str, float]]:
    """The annualised return of every ``months`` window, by window end date."""
    dates, navs, _, _ = valid_series(points)
    if len(dates) < 2:
        return []
    return [(_iso(dates[j]), value) for j, value in window_points(dates, navs, months, True)]


def month_end_navs(points: Points, months: int) -> list[tuple[str, float]]:
    """The last valid NAV of each calendar month, for the last ``months`` months.

    A small trend line for cards and table rows: NAVs as filed, nothing derived.
    """
    dates, navs, _, _ = valid_series(points)
    if not dates:
        return []
    last = date.fromordinal(dates[-1])
    first_key = last.year * 12 + last.month - 1 - months
    found: dict[int, tuple[str, float]] = {}
    for day, nav in zip(dates, navs, strict=True):
        moment = date.fromordinal(day)
        key = moment.year * 12 + moment.month - 1
        if key >= first_key:
            found[key] = (moment.isoformat(), nav)
    return [found[k] for k in sorted(found)]


def drawdowns(points: Points, top: int) -> list[dict[str, Any]]:
    """The ``top`` deepest falls from a peak, each with its trough and recovery (or none)."""
    dates, navs, _, _ = valid_series(points)
    found: list[tuple[float, int, int, int | None]] = []
    peak, trough = 0, None
    for k in range(1, len(navs)):
        if navs[k] >= navs[peak]:
            if trough is not None:
                found.append((navs[trough] / navs[peak] - 1, peak, trough, k))
                trough = None
            peak = k
        elif trough is None or navs[k] < navs[trough]:
            trough = k
    if trough is not None:
        found.append((navs[trough] / navs[peak] - 1, peak, trough, None))
    found.sort(key=lambda e: (e[0], e[1]))
    return [
        {
            "depth": depth,
            "peak": _iso(dates[p]),
            "trough": _iso(dates[t]),
            "recovery": None if r is None else _iso(dates[r]),
            "fall_days": dates[t] - dates[p],
            "recovery_days": None if r is None else dates[r] - dates[t],
        }
        for depth, p, t, r in found[:top]
    ]


def correlation(first: Points, second: Points) -> tuple[float | None, int]:
    """Pearson correlation of returns between consecutive common NAV dates, and their count."""
    a_dates, a_navs, _, _ = valid_series(first)
    b_dates, b_navs, _, _ = valid_series(second)
    a, b = dict(zip(a_dates, a_navs, strict=True)), dict(zip(b_dates, b_navs, strict=True))
    common = sorted(a.keys() & b.keys())
    x = [a[d] / a[c] - 1 for c, d in zip(common, common[1:], strict=False)]
    y = [b[d] / b[c] - 1 for c, d in zip(common, common[1:], strict=False)]
    if len(x) < MIN_OBSERVATIONS:
        return None, len(x)
    mx, my = math.fsum(x) / len(x), math.fsum(y) / len(y)
    sxy = math.fsum((p - mx) * (q - my) for p, q in zip(x, y, strict=True))
    sxx = math.fsum((p - mx) ** 2 for p in x)
    syy = math.fsum((q - my) ** 2 for q in y)
    if sxx == 0 or syy == 0:
        return None, len(x)
    return sxy / math.sqrt(sxx * syy), len(x)


def underwater(points: Points) -> list[tuple[str, float]]:
    """Each valid NAV's fall from the highest NAV so far (0 at a new peak)."""
    dates, navs, _, _ = valid_series(points)
    found: list[tuple[str, float]] = []
    peak = 0.0
    for day, nav in zip(dates, navs, strict=True):
        peak = max(peak, nav)
        found.append((_iso(day), nav / peak - 1))
    return found


def recovery_spread(episodes: Sequence[dict[str, Any]], depth: float) -> dict[str, Any]:
    """Recovery times of recovered falls at least ``depth`` deep: count and nearest-rank spread."""
    days = sorted(e["recovery_days"] for e in episodes if e["depth"] <= depth and e["recovery"])
    open_falls = sum(1 for e in episodes if e["depth"] <= depth and not e["recovery"])
    spread: dict[str, Any] = {"depth": depth, "recovered": len(days), "not_recovered": open_falls}
    if days:
        spread |= {
            "min_days": days[0],
            "median_days": nearest_rank(days, 0.5),
            "p90_days": nearest_rank(days, 0.9),
            "max_days": days[-1],
        }
    return spread


def rolling_sip(
    points: Points, as_of: int, months: int, amount: float, day: int, step_up: float
) -> list[dict[str, Any]]:
    """A SIP of ``months`` instalments started in every month with a full tenor.

    A start counts when the fund has a valid NAV on or before the start date and the
    tenor ends on or before ``as_of``. SIP drawdown is the lowest value ÷ invested − 1
    on the instalment dates.
    """
    dates, _, _, _ = valid_series(points)
    if not dates:
        return []
    first, last = date.fromordinal(dates[0]), date.fromordinal(as_of)
    year, month = (first.year, first.month + 1) if first.day > 1 else (first.year, first.month)
    found: list[dict[str, Any]] = []
    while True:
        year, month = (year + 1, month - 12) if month > 12 else (year, month)
        start = date(year, month, 1)
        end_year, end_month = divmod(year * 12 + month - 1 + months, 12)
        end = date(end_year, end_month + 1, 1).toordinal() - 1
        if end > as_of or start > last:
            return found
        outcome = calculators.sip(
            points, amount, day, start, date.fromordinal(end), step_up=step_up
        )
        summary = outcome.summary
        found.append(
            {
                "start": start.isoformat(),
                "end": summary["valued_on"],
                "invested": summary["invested"],
                "value": summary["value"],
                "xirr": summary["xirr"],
                "sip_drawdown": min(t["value"] / t["invested"] - 1 for t in outcome.timeline),
            }
        )
        month += 1


def frontier(points: Sequence[tuple[str, float, float]]) -> set[str]:
    """Codes no other point beats on both axes: lower risk and higher return.

    ``points`` are (code, risk, return). A point is dominated when another has risk
    no higher and return no lower, and is strictly better on one.
    """
    best: set[str] = set()
    top = -math.inf
    for code, _, ret in sorted(points, key=lambda p: (p[1], -p[2], p[0])):
        if ret > top:
            best.add(code)
            top = ret
    return best
