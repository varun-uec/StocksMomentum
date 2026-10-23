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

from wickstreet.analytics.domain.metrics import (
    Missing,
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
