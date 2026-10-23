"""Cross-fund metrics: category ranks, consistency, persistence and the score (method v4).

A peer group is canonical category × plan × option. Its members are every fund of
that key with a valid NAV, including funds that stopped publishing, so a past
month-end ranks the funds alive then, not only the survivors (doc 21 M1). Today's
ranks and every field are written for active members only. Unclassified funds have
no group. Ranks need ``MIN_PEERS`` funds with a value; ties share a rank and split
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
    MonthEnds,
    Value,
)

MIN_PEERS = 5
MIN_MONTHS = 12
# Persistence looks back over this many complete month-ends.
PERSISTENCE_MONTHS = 36
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
# Ranked again one year before the as-of date, among the funds alive then (doc 21 M10).
THEN_METRICS = (("ret_1y", True), ("vol_3y", False), ("mdd_3y", True))
PERSISTENCE = ("q1_share_3y", "pct_mean_3y")
DETERIORATION = (
    *(f"{name}_cat_pct_1y_ago" for name, _ in THEN_METRICS),
    "ret_1y_cat_quartile_1y_ago",
    *(f"{name}_pct_chg_1y" for name, _ in THEN_METRICS),
    "quartile_change_1y",
    "consistency_3y_chg_1y",
)
PEER_FIELDS = (
    "consistency_3y",
    *(f"{name}_{stat}" for name, _ in PEER_METRICS for stat in PEER_STATS),
    *PERSISTENCE,
    *DETERIORATION,
)


@dataclass(slots=True)
class PeerFund:
    """One group member: ranked inputs (then peer fields), month-ends, year-ago values."""

    values: dict[str, Value]
    month_ends: MonthEnds
    then: dict[str, float]
    active: bool


@dataclass(frozen=True, slots=True)
class Rank:
    """A value's place among its peers."""

    rank: int
    pct: float
    quartile: int
    count: int


def _median(ordered: Sequence[float]) -> float:
    n = len(ordered)
    return ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2


def quartile(pct: float) -> int:
    """1 when the percentile is 75 or more, 2 from 50, 3 from 25, else 4."""
    return 1 if pct >= 75 else 2 if pct >= 50 else 3 if pct >= 25 else 4


def rank_all(values: Sequence[float], higher: bool) -> list[Rank]:
    """Each value's rank (1 + peers strictly better) and percentile (100 = best)."""
    ordered = sorted(values)
    n = len(ordered)
    ranks = []
    for value in values:
        below, above = bisect_left(ordered, value), n - bisect_right(ordered, value)
        better, worse = (above, below) if higher else (below, above)
        pct = 100 * (worse + 0.5 * (n - 1 - better - worse)) / (n - 1)
        ranks.append(Rank(1 + better, pct, quartile(pct), n))
    return ranks


def _by_month(members: Sequence[PeerFund], series: str) -> dict[int, list[tuple[int, float]]]:
    found: dict[int, list[tuple[int, float]]] = defaultdict(list)
    for i, fund in enumerate(members):
        ends = fund.month_ends
        for month, value in zip(ends.months, getattr(ends, series), strict=True):
            if not math.isnan(value):
                found[month].append((i, value))
    return found


def monthly_ranks(members: Sequence[PeerFund], series: str) -> list[dict[int, Rank]]:
    """Per member: month -> its rank on ``series`` among the members alive that month."""
    found: list[dict[int, Rank]] = [{} for _ in members]
    for month, pairs in _by_month(members, series).items():
        if len(pairs) >= MIN_PEERS:
            for (i, _), rank in zip(pairs, rank_all([v for _, v in pairs], True), strict=True):
                found[i][month] = rank
    return found


def transitions(ranks: Sequence[dict[int, Rank]], months: int = 12) -> list[list[int]]:
    """Counts of (quartile at a month-end, quartile ``months`` later), rows = from quartile."""
    counts = [[0] * 4 for _ in range(4)]
    for by_month in ranks:
        for month, rank in by_month.items():
            later = by_month.get(month + months)
            if later is not None:
                counts[rank.quartile - 1][later.quartile - 1] += 1
    return counts


def _consistency(members: Sequence[PeerFund], last_month: int) -> None:
    """Share of month-ends whose 3Y CAGR beats the median of the members alive that month.

    Written now and as it stood 12 months earlier, for active members.
    """
    medians = {
        m: _median(sorted(v for _, v in pairs))
        for m, pairs in _by_month(members, "cagr_3y").items()
        if len(pairs) >= MIN_PEERS
    }
    for fund in members:
        if not fund.active:
            continue
        ends = fund.month_ends
        compared = [
            (m, value > medians[m])
            for m, value in zip(ends.months, ends.cagr_3y, strict=True)
            if m in medians and not math.isnan(value)
        ]
        for name, until in (("consistency_3y", last_month), ("_consistency_then", last_month - 12)):
            beats = [b for m, b in compared if m <= until]
            fund.values[name] = (
                sum(beats) / len(beats)
                if len(beats) >= MIN_MONTHS
                else Missing("NA", HISTORY_TOO_SHORT)
            )


def _persistence(fund: PeerFund, by_month: dict[int, Rank], last_month: int) -> None:
    """Top-quartile share and mean percentile of the 1Y return over the last 36 month-ends."""
    first = last_month - PERSISTENCE_MONTHS + 1
    ranked = [by_month[m] for m in range(first, last_month + 1) if m in by_month]
    if len(ranked) < MIN_MONTHS:
        fund.values |= dict.fromkeys(PERSISTENCE, Missing("NA", HISTORY_TOO_SHORT))
        return
    fund.values["q1_share_3y"] = sum(1 for r in ranked if r.quartile == 1) / len(ranked)
    fund.values["pct_mean_3y"] = math.fsum(r.pct for r in ranked) / len(ranked)


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
    values = [float(f.values[name]) for f in ranked]  # type: ignore[arg-type]
    median = _median(sorted(values))
    for fund, rank in zip(ranked, rank_all(values, higher), strict=True):
        fund.values |= {
            f"{name}_cat_rank": rank.rank,
            f"{name}_cat_pct": rank.pct,
            f"{name}_cat_quartile": rank.quartile,
            f"{name}_cat_count": rank.count,
            f"{name}_cat_median": median,
        }


def _change(now: Value, then: Value) -> Value:
    if isinstance(now, Missing):
        return now
    if isinstance(then, Missing):
        return then
    return float(now) - float(then)


def _year_ago(members: Sequence[PeerFund], subjects: Sequence[PeerFund]) -> None:
    """Percentiles among the members alive a year ago, and the change since (doc 21 M10)."""
    for name, higher in THEN_METRICS:
        key = f"{name}_cat_pct_1y_ago"
        alive = [f for f in members if name in f.then]
        absent = Missing("NA", TOO_FEW_PEERS if len(alive) < MIN_PEERS else HISTORY_TOO_SHORT)
        for fund in subjects:
            fund.values[key] = absent
            if name == "ret_1y":
                fund.values["ret_1y_cat_quartile_1y_ago"] = absent
        if len(alive) >= MIN_PEERS:
            for fund, rank in zip(
                alive, rank_all([f.then[name] for f in alive], higher), strict=True
            ):
                if fund.active:
                    fund.values[key] = rank.pct
                    if name == "ret_1y":
                        fund.values["ret_1y_cat_quartile_1y_ago"] = rank.quartile
        for fund in subjects:
            fund.values[f"{name}_pct_chg_1y"] = _change(
                fund.values[f"{name}_cat_pct"], fund.values[key]
            )
    for fund in subjects:
        fund.values["quartile_change_1y"] = _change(
            fund.values["ret_1y_cat_quartile_1y_ago"], fund.values["ret_1y_cat_quartile"]
        )
        fund.values["consistency_3y_chg_1y"] = _change(
            fund.values["consistency_3y"], fund.values.pop("_consistency_then")
        )


def _score(fund: PeerFund) -> None:
    parts = [fund.values[f"{name}_cat_pct"] for name in SCORE_PARTS]
    missing = next((p for p in parts if isinstance(p, Missing)), None)
    fund.values["score"] = (
        missing if missing is not None else math.fsum(float(p) for p in parts) / len(parts)  # type: ignore[arg-type]
    )


def add_group_fields(members: Sequence[PeerFund], last_month: int) -> None:
    """Write every peer field of the group's active members.

    ``last_month`` is the key of the last complete month on or before the as-of date.
    """
    subjects = [f for f in members if f.active]
    _consistency(members, last_month)
    for fund, by_month in zip(members, monthly_ranks(members, "ret_1y"), strict=True):
        if fund.active:
            _persistence(fund, by_month, last_month)
    for name, higher in PEER_METRICS:
        if name == "score":
            for fund in subjects:
                _score(fund)
        _rank(subjects, name, higher)
    _year_ago(members, subjects)


def absent_fields(absent: Missing) -> dict[str, Value]:
    """The peer fields of a fund with no group."""
    return dict.fromkeys((*PEER_FIELDS, "score"), absent)


def group_absence(status: str, category: str, unclassified: str) -> Missing | None:
    """Why a fund has no peer fields, or ``None`` when it has them."""
    if status != "active":
        return Missing("NA", status if status == "no_nav" else "no_recent_nav")
    if category == unclassified:
        return Missing("NA", NO_PEER_GROUP)
    return None
