"""Portfolio intelligence from the ledger (doc 21 C25, C26; Slice 6).

Cash flows are the investor's: money in is negative. A purchase, switch in or reversal
contributes minus its filed amount; a redemption or switch out plus its filed amount
(the statement files it negative); a dividend payout is money out of the fund; stamp
duty, STT and TDS are money the investor paid. A reinvested dividend moves no cash.
Value is units times the fund's latest stored NAV. XIRR solves the dated flows plus
today's value. Units the ledger computes are checked against the statement's closing
balance; a gap is reported, never smoothed.
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from wickstreet.analytics.domain.calculators import xirr
from wickstreet.analytics.domain.holdings import cap_of, overlap
from wickstreet.mf_data.domain.reads import Portfolio
from wickstreet.portfolio.domain.model import (
    CASH_IN,
    CASH_OUT,
    PAYOUT,
    TAXES,
    Closing,
    Transaction,
)

# Units closer than this agree with the statement (CAS files units to 3 decimals).
UNIT_TOLERANCE = Decimal("0.001")
ZERO_UNITS = Decimal("0.0005")
_FLOW_KINDS = CASH_IN | CASH_OUT | {"REVERSAL"}
_LOOK_THROUGH = ("equity", "debt", "other")


@dataclass(frozen=True, slots=True)
class FundView:
    """What the research snapshot knows about one held plan-option."""

    code: str
    name: str
    category: str
    asset_class: str
    plan: str
    nav: float | None
    nav_date: date | None
    ter: float | None
    direct_ter: float | None = None
    score: float | None = None
    holdings: Portfolio | None = None


@dataclass(slots=True)
class Position:
    """One scheme in one folio: units, money in and out, value and return."""

    folio: str
    scheme: str
    code: str | None
    isin: str | None
    units: Decimal = Decimal(0)
    invested: float = 0.0
    withdrawn: float = 0.0
    flows: list[tuple[int, float]] = field(default_factory=list)
    value: float | None = None
    xirr: float | None = None
    closing_units: Decimal | None = None
    reconciled: bool | None = None


def flow_of(t: Transaction) -> float:
    """The investor's cash flow of one line; 0 when no money moved."""
    if t.amount is None:
        return 0.0
    amount = float(t.amount)
    if t.kind in _FLOW_KINDS:
        return -amount
    if t.kind == PAYOUT:
        return abs(amount)
    if t.kind in TAXES:
        return -abs(amount)
    return 0.0


def _key(folio: str, code: str | None, isin: str | None, scheme: str) -> tuple[str, str]:
    return folio, code or isin or scheme


def positions(
    transactions: Sequence[Transaction],
    closings: Sequence[Closing],
    funds: Mapping[str, FundView],
    as_of: date,
) -> list[Position]:
    """Every position the ledger holds or has held, with value and XIRR where known."""
    found: dict[tuple[str, str], Position] = {}
    for t in sorted(transactions, key=lambda t: t.day):
        key = _key(t.folio, t.amfi_code, t.isin, t.scheme)
        p = found.setdefault(key, Position(t.folio, t.scheme, t.amfi_code, t.isin))
        p.units += t.units or Decimal(0)
        flow = flow_of(t)
        if flow:
            p.flows.append((t.day.toordinal(), flow))
            if flow < 0:
                p.invested -= flow
            else:
                p.withdrawn += flow
    for c in closings:
        key = _key(c.folio, c.amfi_code, c.isin, c.scheme)
        p = found.setdefault(key, Position(c.folio, c.scheme, c.amfi_code, c.isin))
        p.closing_units = c.units
        p.reconciled = abs(p.units - c.units) <= UNIT_TOLERANCE
    for p in found.values():
        fund = funds.get(p.code or "")
        if p.units <= ZERO_UNITS:
            p.value = 0.0
        elif fund is not None and fund.nav is not None:
            p.value = float(p.units) * fund.nav
        if p.value is not None:
            terminal = [(as_of.toordinal(), p.value)] if p.value > 0 else []
            p.xirr = xirr(sorted(p.flows + terminal))
    return sorted(found.values(), key=lambda p: (-(p.value or 0), p.scheme, p.folio))


def _shares(values: Mapping[str, float]) -> dict[str, float]:
    total = math.fsum(values.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in sorted(values.items(), key=lambda kv: (-kv[1], kv[0]))}


def summary(held: Sequence[Position], funds: Mapping[str, FundView], as_of: date) -> dict[str, Any]:
    """Totals, XIRR, allocation, costs and the reconciliation of the whole portfolio."""
    live = [p for p in held if p.value]
    valued = [p for p in held if p.units > ZERO_UNITS and p.value is None]
    value = math.fsum(p.value or 0 for p in live)
    flows = sorted(
        [f for p in held for f in p.flows] + ([(as_of.toordinal(), value)] if value else [])
    )
    by: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    cost = saving = with_ter = 0.0
    for p in live:
        fund = funds.get(p.code or "")
        v = p.value or 0.0
        by["asset_class"][fund.asset_class if fund else "Unknown"] += v
        by["category"][fund.category if fund else "Unknown"] += v
        by["plan"][fund.plan if fund else "Unknown"] += v
        if fund and fund.ter is not None:
            cost += v * fund.ter
            with_ter += v
            if fund.plan == "regular" and fund.direct_ter is not None:
                saving += v * max(fund.ter - fund.direct_ter, 0.0)
    invested = math.fsum(p.invested for p in held)
    withdrawn = math.fsum(p.withdrawn for p in held)
    checked = [p for p in held if p.reconciled is not None]
    return {
        "as_of": as_of.isoformat(),
        "value": value,
        "invested": invested,
        "withdrawn": withdrawn,
        "gain": value + withdrawn - invested,
        "xirr": xirr(flows),
        "positions": len(live),
        "unvalued": [p.scheme for p in valued],
        "allocation": {k: _shares(v) for k, v in by.items()},
        "costs": {
            "weighted_ter": cost / with_ter if with_ter else None,
            "annual_cost": cost,
            "ter_coverage": with_ter / value if value else None,
            "regular_plan_share": _shares(by["plan"]).get("regular", 0.0),
            "direct_switch_saving": saving,
        },
        "reconciliation": {
            "checked": len(checked),
            "matched": sum(1 for p in checked if p.reconciled),
            "gaps": [
                {
                    "scheme": p.scheme,
                    "folio": p.folio,
                    "ledger": str(p.units),
                    "statement": str(p.closing_units),
                }
                for p in checked
                if not p.reconciled
            ],
        },
    }


def look_through(
    held: Sequence[Position], funds: Mapping[str, FundView], caps: Any
) -> dict[str, Any]:
    """Securities, sectors and market cap across funds, weighted by value."""
    total = math.fsum(p.value or 0 for p in held)
    securities: dict[str, list[Any]] = {}
    sectors: dict[str, float] = defaultdict(float)
    cap_mix: dict[str, float] = defaultdict(float)
    covered = 0.0
    for p in held:
        fund = funds.get(p.code or "")
        if not p.value or total <= 0 or fund is None or fund.holdings is None:
            continue
        share = p.value / total
        covered += share
        for r in fund.holdings.rows:
            if r.asset not in _LOOK_THROUGH:
                continue
            key = r.isin or r.name
            entry = securities.setdefault(key, [r.name, r.isin, 0.0, set()])
            entry[2] += share * r.weight
            entry[3].add(fund.code)
            if r.asset == "equity":
                sectors[r.industry or "Not filed"] += share * r.weight
                cap_mix[cap_of(r.isin, fund.holdings.as_of, caps)] += share * r.weight
    top = sorted(securities.values(), key=lambda e: (-e[2], e[0]))[:20]
    return {
        "coverage": covered,
        "securities": [
            {"name": n, "isin": i, "weight": w, "funds": sorted(f)} for n, i, w, f in top
        ],
        "sectors": dict(sorted(sectors.items(), key=lambda kv: (-kv[1], kv[0]))[:12]),
        "market_cap": dict(sorted(cap_mix.items(), key=lambda kv: (-kv[1], kv[0]))),
    }


def fund_overlaps(funds: Sequence[FundView]) -> list[dict[str, Any]]:
    """Weighted overlap of each pair of held funds that both have a portfolio."""
    found = []
    with_holdings = [f for f in funds if f.holdings is not None]
    for i, a in enumerate(with_holdings):
        for b in with_holdings[i + 1 :]:
            result = overlap(a.holdings, b.holdings)  # type: ignore[arg-type]
            found.append(
                {
                    "a": a.code,
                    "b": b.code,
                    "weighted_overlap": result["weighted_overlap"],
                    "common_count": result["common_count"],
                    "same_month": result["same_month"],
                    "top": result["common"][:5],
                }
            )
    return sorted(found, key=lambda x: -x["weighted_overlap"])


def rebalance(
    current: Mapping[str, float], value: float, target: Mapping[str, float]
) -> list[dict[str, Any]]:
    """The amount to buy (positive) or sell per asset class to reach ``target`` shares."""
    classes = sorted(set(current) | set(target))
    return [
        {
            "asset_class": c,
            "current": current.get(c, 0.0),
            "target": target.get(c, 0.0),
            "trade": (target.get(c, 0.0) - current.get(c, 0.0)) * value,
        }
        for c in classes
    ]
