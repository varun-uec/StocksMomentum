"""Holdings analytics from monthly portfolio disclosures (doc 21 C16, C25; method v6).

Weights are fractions of net assets as filed. A line is a security by its ISIN, else
by its filed name. Market cap uses AMFI's list for the latest half-year ending on or
before the portfolio date. Equity statistics (concentration, sectors, market cap) are
over equity lines only, rescaled to sum to 1, so a fund with 20% cash is compared on
the equity it holds.
"""

from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from wickstreet.analytics.domain.fieldspec import Field
from wickstreet.analytics.domain.metrics import NO_EQUITY, NOT_FILED, Missing, Value
from wickstreet.mf_data.domain.reads import HoldingRow, Portfolio

ASSETS = ("equity", "debt", "cash", "derivative", "other")
CAP_CLASSES = ("Large Cap", "Mid Cap", "Small Cap")
FOREIGN, UNLISTED = "Foreign", "Not in AMFI's list"
# A portfolio whose weights sum this far from 1 is flagged, not dropped.
RECONCILE_TOLERANCE = 0.02
TOP = 10

HOLDING_FIELDS = (
    Field(
        "holdings_as_of", "Portfolio date", "Holdings", "date", None, "Latest monthly disclosure."
    ),
    Field("holdings_count", "Holdings", "Holdings", "number", "count", "Lines with a weight."),
    Field(
        "top10_weight",
        "Top 10 holdings",
        "Holdings",
        "number",
        "fraction",
        "Weight of the ten largest lines.",
    ),
    Field(
        "effective_holdings",
        "Effective number of stocks",
        "Holdings",
        "number",
        None,
        "1 ÷ the sum of squared equity weights: how many equal stocks the spread equals.",
    ),
    *(
        Field(
            f"{a}_share",
            f"{a.capitalize()} share",
            "Holdings",
            "number",
            "fraction",
            f"Weight of {a} lines.",
        )
        for a in ("equity", "debt", "cash")
    ),
    *(
        Field(
            f"{c.split()[0].lower()}_cap_share",
            f"{c} share of equity",
            "Holdings",
            "number",
            "fraction",
            f"{c} stocks by AMFI's list, as a share of the equity held.",
        )
        for c in CAP_CLASSES
    ),
    Field(
        "foreign_share",
        "Foreign share of equity",
        "Holdings",
        "number",
        "fraction",
        "Equity lines with a non-Indian ISIN.",
    ),
)
HOLDING_FIELD_IDS = tuple(f.id for f in HOLDING_FIELDS)


def key(row: HoldingRow) -> str:
    """A security's identity across funds and months."""
    return row.isin or f"name:{row.name.strip().lower()}"


def cap_of(isin: str | None, day: date, caps: Mapping[str, Sequence[tuple[date, str]]]) -> str:
    """An equity ISIN's class in the latest AMFI list on or before ``day``."""
    if not isin or not isin.startswith("IN"):
        return FOREIGN
    found = caps.get(isin, ())
    at = bisect_right([d for d, _ in found], day) - 1
    if at < 0:
        return UNLISTED
    return found[at][1]


def _equity(rows: Sequence[HoldingRow]) -> list[tuple[HoldingRow, float]]:
    equity = [r for r in rows if r.asset == "equity" and r.weight > 0]
    total = sum(r.weight for r in equity)
    return [(r, r.weight / total) for r in equity] if total > 0 else []


def summary(portfolio: Portfolio, caps: Mapping[str, Sequence[tuple[date, str]]]) -> dict[str, Any]:
    """Asset mix, concentration, sectors and market cap of one portfolio."""
    rows = portfolio.rows
    assets = dict.fromkeys(ASSETS, 0.0)
    for r in rows:
        assets[r.asset] = assets.get(r.asset, 0.0) + r.weight
    equity = _equity(rows)
    sectors: dict[str, float] = defaultdict(float)
    cap_mix: dict[str, float] = defaultdict(float)
    for r, w in equity:
        sectors[r.industry or "Not filed"] += w
        cap_mix[cap_of(r.isin, portfolio.as_of, caps)] += w
    ratings: dict[str, float] = defaultdict(float)
    for r in rows:
        if r.asset == "debt":
            ratings[r.industry or "Not filed"] += r.weight
    ordered = sorted(rows, key=lambda r: (-r.weight, r.name))
    # AMCs file a hedge's short futures as notional lines outside the 100%, but count
    # long futures and options in it; the closer of the two totals is the check.
    total = min(
        (sum(r.weight for r in rows), sum(r.weight for r in rows if r.asset != "derivative")),
        key=lambda t: abs(t - 1),
    )
    return {
        "as_of": portfolio.as_of.isoformat(),
        "count": len(rows),
        "weight_sum": total,
        "reconciled": abs(total - 1) <= RECONCILE_TOLERANCE,
        "assets": assets,
        "top10_weight": sum(r.weight for r in ordered[:TOP]),
        "effective_holdings": 1 / sum(w * w for _, w in equity) if equity else None,
        "sectors": dict(sorted(sectors.items(), key=lambda kv: (-kv[1], kv[0]))),
        "market_cap": {c: cap_mix.get(c, 0.0) for c in (*CAP_CLASSES, FOREIGN, UNLISTED)},
        "ratings": dict(sorted(ratings.items(), key=lambda kv: (-kv[1], kv[0]))),
    }


def holding_fields(
    portfolio: Portfolio | None, caps: Mapping[str, Sequence[tuple[date, str]]]
) -> dict[str, Value]:
    """The screenable holdings fields of one scheme's latest portfolio."""
    if portfolio is None:
        return dict.fromkeys(HOLDING_FIELD_IDS, Missing("NA", NOT_FILED))
    s = summary(portfolio, caps)
    cap = s["market_cap"]
    equity = s["assets"]["equity"] > 0
    absent = Missing("NM", NO_EQUITY)

    def share(value: float) -> Value:
        return value if equity else absent

    return {
        "holdings_as_of": s["as_of"],
        "holdings_count": s["count"],
        "top10_weight": s["top10_weight"],
        "effective_holdings": s["effective_holdings"] if equity else absent,
        "equity_share": s["assets"]["equity"],
        "debt_share": s["assets"]["debt"],
        "cash_share": s["assets"]["cash"],
        "large_cap_share": share(cap["Large Cap"]),
        "mid_cap_share": share(cap["Mid Cap"]),
        "small_cap_share": share(cap["Small Cap"]),
        "foreign_share": share(cap[FOREIGN]),
    }


def by_size(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Largest weight change first, then by name."""
    return sorted(items, key=lambda x: (-abs(x["change"]), x["name"]))


def changes(before: Portfolio, after: Portfolio) -> dict[str, list[dict[str, Any]]]:
    """Lines added, removed, and the largest weight moves between two disclosures."""
    old = {key(r): r for r in before.rows}
    new = {key(r): r for r in after.rows}

    def line(r: HoldingRow, was: float, now: float) -> dict[str, Any]:
        return {"name": r.name, "isin": r.isin, "before": was, "after": now, "change": now - was}

    added = [line(r, 0.0, r.weight) for k, r in new.items() if k not in old]
    removed = [line(r, r.weight, 0.0) for k, r in old.items() if k not in new]
    moved = [line(r, old[k].weight, r.weight) for k, r in new.items() if k in old]
    return {
        "added": by_size(added),
        "removed": by_size(removed),
        "increased": by_size([m for m in moved if m["change"] > 0])[:TOP],
        "decreased": by_size([m for m in moved if m["change"] < 0])[:TOP],
    }


def overlap(a: Portfolio, b: Portfolio) -> dict[str, Any]:
    """Common securities and weighted overlap: the sum over shared lines of the smaller weight.

    Lines are matched by ISIN (else filed name), and cash, TREPS and derivatives are left
    out, so two funds do not overlap by both holding cash.
    """
    kept = ("equity", "debt", "other")

    def weights(p: Portfolio) -> dict[str, tuple[HoldingRow, float]]:
        found: dict[str, tuple[HoldingRow, float]] = {}
        for r in p.rows:
            if r.asset in kept:
                held = found.get(key(r))
                found[key(r)] = (r, (held[1] if held else 0.0) + r.weight)
        return found

    wa, wb = weights(a), weights(b)
    shared = sorted(wa.keys() & wb.keys(), key=lambda k: (-min(wa[k][1], wb[k][1]), wa[k][0].name))
    common: list[dict[str, Any]] = [
        {"name": wa[k][0].name, "isin": wa[k][0].isin, "a": wa[k][1], "b": wb[k][1]} for k in shared
    ]
    sa, sb = summary(a, {}), summary(b, {})
    sectors = sa["sectors"].keys() & sb["sectors"].keys()
    return {
        "a_as_of": a.as_of.isoformat(),
        "b_as_of": b.as_of.isoformat(),
        "same_month": (a.as_of.year, a.as_of.month) == (b.as_of.year, b.as_of.month),
        "common_count": len(common),
        "weighted_overlap": sum(min(wa[k][1], wb[k][1]) for k in shared),
        "sector_overlap": sum(min(sa["sectors"][s], sb["sectors"][s]) for s in sectors),
        "common": common,
    }


def trend(
    portfolios: Sequence[Portfolio], caps: Mapping[str, Sequence[tuple[date, str]]]
) -> list[dict[str, Any]]:
    """Asset mix, concentration and market cap of each disclosure, oldest first."""
    found = []
    for p in portfolios:
        s = summary(p, caps)
        found.append(
            {
                "as_of": s["as_of"],
                **{f"{a}": s["assets"][a] for a in ("equity", "debt", "cash")},
                "top10_weight": s["top10_weight"],
                "effective_holdings": s["effective_holdings"],
                **{c: s["market_cap"][c] for c in CAP_CLASSES},
                "count": s["count"],
            }
        )
    return found
