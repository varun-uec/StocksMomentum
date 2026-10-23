"""Point-in-time selection backtests over one peer group (method v4, doc 21 C10, M14).

At each complete month-end the strategy ranks the group's funds alive that month on a
signal known then, holds the top ``top`` with equal weights for one month, and is
compared with the median next-month return of every fund alive at both month-ends.
Returns are NAV returns, net of TER, before tax. Months before ``HOLDOUT_FROM`` are
in-sample; from it on they are the hold-out. The strategy fits no parameter, so the
split only reports both periods apart.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from wickstreet.analytics.domain.metrics import MonthEnds

SIGNALS = ("ret_1y", "cagr_3y")
MIN_FUNDS = 5
MAX_TOP = 50
HOLDOUT_FROM = 2024 * 12  # January 2024, as a month key
LIMITS = (
    "Peer groups use AMFI's current category for past dates.",
    "Closed funds with labels that map to no category are in no group.",
    "A fund whose AMFI code changed has a short history under its new code.",
    "A pick with no NAV at the next month-end is dropped that month.",
)


class BacktestError(ValueError):
    """The request cannot be backtested."""


@dataclass(frozen=True, slots=True)
class Month:
    """One holding month: the signal month-end, picks, and both returns."""

    month: int
    picks: tuple[str, ...]
    strategy: float
    median: float


def _key(month: int) -> str:
    year, index = divmod(month, 12)
    return f"{year:04d}-{index + 1:02d}"


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    return ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2


def run(members: Mapping[str, MonthEnds], signal: str, top: int) -> list[Month]:
    """Every holding month of the strategy; ``members`` maps AMFI code -> month-ends."""
    if signal not in SIGNALS:
        raise BacktestError(f"signal is one of {', '.join(SIGNALS)}")
    if not 1 <= top <= MAX_TOP:
        raise BacktestError(f"top is 1 to {MAX_TOP}")
    by_month: dict[int, dict[str, tuple[float, float]]] = {}
    for code, ends in members.items():
        for month, nav, value in zip(ends.months, ends.navs, getattr(ends, signal), strict=True):
            by_month.setdefault(month, {})[code] = (nav, value)
    found: list[Month] = []
    for month in sorted(by_month):
        now, later = by_month[month], by_month.get(month + 1)
        if later is None:
            continue
        ranked = sorted(
            ((value, code) for code, (_, value) in now.items() if not math.isnan(value)),
            key=lambda p: (-p[0], p[1]),
        )
        if len(ranked) < MIN_FUNDS:
            continue
        returns = {c: later[c][0] / now[c][0] - 1 for c in now if c in later}
        if len(returns) < MIN_FUNDS:
            continue
        picks = [code for _, code in ranked[:top] if code in returns]
        if not picks:
            continue
        found.append(
            Month(
                month,
                tuple(picks),
                math.fsum(returns[c] for c in picks) / len(picks),
                _median(list(returns.values())),
            )
        )
    return found


def _period(months: Sequence[Month]) -> dict[str, Any]:
    if not months:
        return {"months": 0}
    strategy = math.prod(1 + m.strategy for m in months)
    median = math.prod(1 + m.median for m in months)
    years = len(months) / 12
    return {
        "months": len(months),
        "first_signal": _key(months[0].month),
        "last_signal": _key(months[-1].month),
        "strategy_growth": strategy - 1,
        "median_growth": median - 1,
        "strategy_annualised": strategy ** (1 / years) - 1,
        "median_annualised": median ** (1 / years) - 1,
        "beat_share": sum(1 for m in months if m.strategy > m.median) / len(months),
    }


def summarise(months: Sequence[Month]) -> dict[str, Any]:
    """In-sample, hold-out and whole-period results."""
    return {
        "in_sample": _period([m for m in months if m.month < HOLDOUT_FROM]),
        "holdout": _period([m for m in months if m.month >= HOLDOUT_FROM]),
        "whole": _period(months),
    }


def spanned(months: Sequence[Month], windows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """The regime windows that overlap the holding months (signal month to the next)."""
    if not months:
        return []
    first = f"{_key(months[0].month)}-01"
    last = f"{_key(months[-1].month + 1)}-31"
    return [dict(w) for w in windows if w["end"] >= first and w["start"] <= last]


def rows(months: Sequence[Month]) -> list[dict[str, Any]]:
    """The monthly table."""
    return [
        {
            "signal_month": _key(m.month),
            "picks": list(m.picks),
            "strategy": m.strategy,
            "median": m.median,
        }
        for m in months
    ]
