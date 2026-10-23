"""Cross-fund metrics: category ranks, consistency and the composite score (method v3).

A peer group is canonical category × plan × option, over active funds only, so a
fund that stopped publishing never sets a peer's rank. Unclassified funds have no
group. Ranks need ``MIN_PEERS`` funds with a value; ties share a rank and split
the percentile (average rank).
"""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

from wickstreet.analytics.domain.metrics import (
    HISTORY_TOO_SHORT,
    NO_PEER_GROUP,
    TOO_FEW_PEERS,
    Missing,
    Value,
)

MIN_PEERS = 5
MIN_MONTHS = 12
# (field, higher is better)
PEER_METRICS = (
    ("ret_1y", True),
    ("cagr_3y", True),
    ("cagr_5y", True),
    ("vol_3y", False),
    ("mdd_3y", True),
    ("sortino_3y", True),
    ("ret_risk_3y", True),
    ("consistency_3y", True),
    ("score", True),
)
PEER_STATS = ("cat_rank", "cat_pct", "cat_quartile", "cat_count", "cat_median")
# Inputs a group needs from each member's own metrics.
RANKED_INPUTS = tuple(n for n, _ in PEER_METRICS if n not in ("consistency_3y", "score"))
# Equal weights over these category percentiles (doc 20 §3; cost joins with E1).
SCORE_PARTS = ("consistency_3y", "ret_risk_3y", "mdd_3y")
PEER_FIELDS = (
    "consistency_3y",
    *(f"{name}_{stat}" for name, _ in PEER_METRICS for stat in PEER_STATS),
)


@dataclass(slots=True)
class PeerFund:
    """One grouped fund: its ranked inputs, then its peer fields, and its month-end 3Y."""

    values: dict[str, Value]
    month_ends: Sequence[int]
    rolling_3y: Sequence[float]


def _median(ordered: Sequence[float]) -> float:
    n = len(ordered)
    return ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2


def _consistency(members: Sequence[PeerFund]) -> None:
    """Share of month-ends whose rolling 3Y return beats the group median that month."""
    by_month: dict[int, list[float]] = defaultdict(list)
    for fund in members:
        for month, value in zip(fund.month_ends, fund.rolling_3y, strict=True):
            by_month[month].append(value)
    medians = {m: _median(sorted(v)) for m, v in by_month.items() if len(v) >= MIN_PEERS}
    for fund in members:
        compared = [
            value > medians[m]
            for m, value in zip(fund.month_ends, fund.rolling_3y, strict=True)
            if m in medians
        ]
        fund.values["consistency_3y"] = (
            sum(compared) / len(compared)
            if len(compared) >= MIN_MONTHS
            else Missing("NA", HISTORY_TOO_SHORT)
        )


def _rank(members: Sequence[PeerFund], name: str, higher: bool) -> None:
    keys = [f"{name}_{stat}" for stat in PEER_STATS]
    ranked = [f for f in members if not isinstance(f.values[name], Missing)]
    for fund in members:
        if isinstance(value := fund.values[name], Missing):
            fund.values |= dict.fromkeys(keys, value)
    if len(ranked) < MIN_PEERS:
        few = Missing("NA", TOO_FEW_PEERS)
        for fund in ranked:
            fund.values |= dict.fromkeys(keys, few)
        return
    ordered = sorted(float(f.values[name]) for f in ranked)  # type: ignore[arg-type]
    n = len(ordered)
    median = _median(ordered)
    for fund in ranked:
        value = float(fund.values[name])  # type: ignore[arg-type]
        below, above = bisect_left(ordered, value), n - bisect_right(ordered, value)
        better, worse = (above, below) if higher else (below, above)
        equal = n - 1 - better - worse
        pct = 100 * (worse + 0.5 * equal) / (n - 1)
        fund.values |= {
            f"{name}_cat_rank": 1 + better,
            f"{name}_cat_pct": pct,
            f"{name}_cat_quartile": 1 if pct >= 75 else 2 if pct >= 50 else 3 if pct >= 25 else 4,
            f"{name}_cat_count": n,
            f"{name}_cat_median": median,
        }


def _score(fund: PeerFund) -> None:
    parts = [fund.values[f"{name}_cat_pct"] for name in SCORE_PARTS]
    missing = next((p for p in parts if isinstance(p, Missing)), None)
    fund.values["score"] = (
        missing if missing is not None else math.fsum(float(p) for p in parts) / len(parts)  # type: ignore[arg-type]
    )


def add_group_fields(members: Sequence[PeerFund]) -> None:
    """Write consistency, every category rank and the score for one peer group."""
    _consistency(members)
    for name, higher in PEER_METRICS:
        if name == "score":
            for fund in members:
                _score(fund)
        _rank(members, name, higher)


def absent_fields(absent: Missing) -> dict[str, Value]:
    """The peer fields of a fund with no group."""
    return dict.fromkeys((*PEER_FIELDS, "score"), absent)


def group_absence(status: str, category: str, unclassified: str) -> Missing | None:
    """Why a fund has no peer group, or ``None`` when it has one."""
    if status != "active":
        return Missing("NA", status if status == "no_nav" else "no_recent_nav")
    if category == unclassified:
        return Missing("NA", NO_PEER_GROUP)
    return None
