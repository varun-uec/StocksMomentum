"""Capital-gains tax on simulated redemptions (rule set ``TAX_RULES``, doc 20 §3).

Rules for sales from 2024-07-23 (Finance (No. 2) Act, 2024):

- **equity** (equity-oriented funds): held over 12 months is long term, taxed at
  12.5% on the financial year's net long-term gain above ₹1.25 lakh; otherwise 20%.
  Units bought before 2018-02-01 use the higher of cost and the 31 Jan 2018 NAV,
  capped at the sale price (grandfathering).
- **debt** (specified funds): units bought from 2023-04-01 are taxed at the slab
  rate whatever the holding period. Older units held over 24 months: 12.5%;
  otherwise the slab rate.
- **other**: held over 24 months: 12.5%; otherwise the slab rate.

Health and education cess of 4% is added. Within a simulation, a financial year's
short-term loss is set off against its long-term gain; nothing carries forward.
Surcharge, exit loads and STT are not modelled. Sales before 2024-07-23 are counted
as not modelled.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal

TAX_RULES = "in-2024-07-23"
RULES_FROM = date(2024, 7, 23).toordinal()
DEBT_SLAB_FROM = date(2023, 4, 1).toordinal()
GRANDFATHER_BEFORE = date(2018, 2, 1).toordinal()
EQUITY_SHORT, LONG_RATE, CESS = 0.20, 0.125, 0.04
EQUITY_EXEMPTION = 125_000.0

TaxClass = Literal["equity", "debt", "other"]
TAX_CLASSES: tuple[TaxClass, ...] = ("equity", "debt", "other")
_EQUITY_HYBRIDS = frozenset(
    {
        "Hybrid Scheme - Aggressive Hybrid Fund",
        "Hybrid Scheme - Arbitrage Fund",
        "Hybrid Scheme - Equity Savings",
    }
)


def tax_class_of(category: str, asset_class: str) -> TaxClass | None:
    """The tax class a category implies, or ``None`` when the fund's own mix decides it."""
    if asset_class == "Equity" or category in _EQUITY_HYBRIDS:
        return "equity"
    if asset_class == "Debt" or category == "Hybrid Scheme - Conservative Hybrid Fund":
        return "debt"
    return None


@dataclass(frozen=True, slots=True)
class Sale:
    """Units of one purchase lot redeemed on one day."""

    bought: int
    sold: int
    units: float
    cost: float
    proceeds: float


@dataclass(frozen=True, slots=True)
class TaxResult:
    """Tax by financial year, the total with cess, or why it could not be computed."""

    rules: str
    total: float | None
    years: list[dict[str, float | str]]
    not_modelled: int
    reason: str | None = None


def _financial_year(ordinal: int) -> str:
    day = date.fromordinal(ordinal)
    start = day.year if day.month >= 4 else day.year - 1
    return f"FY{start}-{(start + 1) % 100:02d}"


def capital_gains_tax(
    sales: Sequence[Sale],
    tax_class: TaxClass | None,
    slab_rate: float | None,
    nav_2018_01_31: float | None,
) -> TaxResult:
    """Tax on ``sales`` under ``TAX_RULES``."""
    if tax_class is None:
        return TaxResult(TAX_RULES, None, [], 0, "tax_class_needed")
    modelled = [s for s in sales if s.sold >= RULES_FROM]
    buckets: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for sale in modelled:
        cost = sale.cost
        if tax_class == "equity" and sale.bought < GRANDFATHER_BEFORE and nav_2018_01_31:
            cost = max(cost, min(nav_2018_01_31 * sale.units, sale.proceeds))
        gain = sale.proceeds - cost
        held = sale.sold - sale.bought
        if tax_class == "equity":
            kind = "long" if held > 365 else "short"
        elif tax_class == "debt" and sale.bought >= DEBT_SLAB_FROM:
            kind = "slab"
        else:
            kind = "long" if held > 730 else "slab"
        buckets[_financial_year(sale.sold)][kind] += gain
    years: list[dict[str, float | str]] = []
    total = 0.0
    for year in sorted(buckets):
        gains = buckets[year]
        short, long, slab = gains["short"], gains["long"], gains["slab"]
        if short < 0:
            long, short = long + short, 0.0
        if slab < 0:
            long, slab = long + slab, 0.0
        if slab > 0 and slab_rate is None:
            return TaxResult(TAX_RULES, None, [], len(sales) - len(modelled), "slab_rate_needed")
        exemption = EQUITY_EXEMPTION if tax_class == "equity" else 0.0
        tax = (
            short * EQUITY_SHORT
            + max(long - exemption, 0.0) * LONG_RATE
            + slab * (slab_rate or 0.0)
        ) * (1 + CESS)
        years.append(
            {"year": year, "short_term": short, "long_term": long, "slab": slab, "tax": tax}
        )
        total += tax
    return TaxResult(TAX_RULES, total, years, len(sales) - len(modelled))
