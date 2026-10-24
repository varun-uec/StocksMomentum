"""Capital-gains tax on simulated redemptions (rule set ``TAX_RULES``, doc 21 M18).

Each sale is taxed under the rules in force on its sale date:

- **from 2024-07-23** (Finance (No. 2) Act, 2024): equity held over 12 months is long
  term at 12.5%, otherwise 20%. Debt units bought from 2023-04-01 pay the slab rate
  whatever the holding period; other debt and ``other`` units held over 24 months pay
  12.5% without indexation, otherwise the slab rate.
- **2018-04-01 to 2024-07-22**: equity held over 12 months is long term at 10%,
  otherwise 15%. Debt units bought from 2023-04-01 pay the slab rate; other debt and
  ``other`` units held over 36 months pay 20% on the indexed gain, otherwise the slab
  rate. Indexed cost = cost × CII of the sale year ÷ CII of the purchase year.

Equity units bought before 2018-02-01 use the higher of cost and the 31 Jan 2018 NAV,
capped at the sale price (grandfathering). The financial year's net long-term equity
gain above ₹1 lakh (₹1.25 lakh from FY2024-25) is taxed, the exemption used against
the highest rate first. Within a financial year, short-term and slab losses offset
long-term gains, highest rate first; a long-term loss offsets only long-term gains.
Nothing carries forward. Health and education cess of 4% is added. Surcharge, exit
loads and STT are not modelled. Sales before 2018-04-01 are counted as not modelled.

Holding periods are calendar months, as the Income-tax Act defines them. A unit held
"over 12 months" is sold after the 12-month anniversary of its purchase date, so a sale
on the anniversary itself is short term. A purchase on a day the anniversary month
lacks (29 Feb, 31st) uses that month's last day.

Overseas equity funds and funds of funds are ``other``. Section 50AA puts their units
bought from 2023-04-01 and sold before 2025-04-01 on the slab rate; no such unit is
held over 24 months, so the ``other`` rules give the same slab treatment. From
2025-04-01 section 50AA no longer covers them and the 24-month rule applies.

The category settles the class only where SEBI's mandate keeps the fund in domestic
equity or in debt. Sectoral and thematic funds may invest wholly overseas (an
international equity fund is filed as thematic), so their class is never inferred.
"""

from __future__ import annotations

import calendar
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Literal

TAX_RULES = "in-2018-04-01"
RULES_FROM = date(2018, 4, 1).toordinal()
FINANCE_ACT_2024 = date(2024, 7, 23).toordinal()
DEBT_SLAB_FROM = date(2023, 4, 1).toordinal()
GRANDFATHER_BEFORE = date(2018, 2, 1).toordinal()
CESS = 0.04
# Cost Inflation Index, by the start year of the financial year (CBDT notifications).
CII = {
    2013: 220,
    2014: 240,
    2015: 254,
    2016: 264,
    2017: 272,
    2018: 280,
    2019: 289,
    2020: 301,
    2021: 317,
    2022: 331,
    2023: 348,
    2024: 363,
}

TaxClass = Literal["equity", "debt", "other"]
TAX_CLASSES: tuple[TaxClass, ...] = ("equity", "debt", "other")
_EQUITY_HYBRIDS = frozenset(
    {
        "Hybrid Scheme - Aggressive Hybrid Fund",
        "Hybrid Scheme - Arbitrage Fund",
        "Hybrid Scheme - Equity Savings",
    }
)
# Equity categories whose mandate allows mostly foreign equity (independent review R-01).
_MAYBE_OVERSEAS = frozenset({"Equity Scheme - Sectoral/ Thematic"})
SHORT, LONG, SLAB = "short", "long", "slab"


def tax_class_of(category: str, asset_class: str) -> TaxClass | None:
    """The tax class a category implies, or ``None`` when the fund's own mix decides it."""
    if category in _MAYBE_OVERSEAS:
        return None
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


def _year_start(ordinal: int) -> int:
    day = date.fromordinal(ordinal)
    return day.year if day.month >= 4 else day.year - 1


def _financial_year(ordinal: int) -> str:
    start = _year_start(ordinal)
    return f"FY{start}-{(start + 1) % 100:02d}"


def held_over(bought: int, sold: int, months: int) -> bool:
    """Whether a unit bought on ``bought`` and sold on ``sold`` was held over ``months``."""
    start = date.fromordinal(bought)
    year, month = divmod(start.month - 1 + months, 12)
    year += start.year
    day = min(start.day, calendar.monthrange(year, month + 1)[1])
    return sold > date(year, month + 1, day).toordinal()


def _treatment(sale: Sale, tax_class: TaxClass) -> tuple[str, float | None, bool]:
    """(term, rate or ``None`` for the slab rate, indexed) for one sale."""
    new = sale.sold >= FINANCE_ACT_2024
    if tax_class == "equity":
        if held_over(sale.bought, sale.sold, 12):
            return LONG, 0.125 if new else 0.10, False
        return SHORT, 0.20 if new else 0.15, False
    if tax_class == "debt" and sale.bought >= DEBT_SLAB_FROM:
        return SLAB, None, False
    if new:
        long = held_over(sale.bought, sale.sold, 24)
        return (LONG, 0.125, False) if long else (SLAB, None, False)
    return (LONG, 0.20, True) if held_over(sale.bought, sale.sold, 36) else (SLAB, None, False)


def _gain(sale: Sale, tax_class: TaxClass, indexed: bool, nav_2018_01_31: float | None) -> float:
    cost = sale.cost
    if tax_class == "equity" and sale.bought < GRANDFATHER_BEFORE and nav_2018_01_31:
        cost = max(cost, min(nav_2018_01_31 * sale.units, sale.proceeds))
    if indexed:
        cost *= CII[_year_start(sale.sold)] / CII[_year_start(sale.bought)]
    return sale.proceeds - cost


def _offset(gains: dict[tuple[str, float], float], loss: float, terms: Sequence[str]) -> None:
    """Take ``loss`` (positive) from the gains of ``terms``, highest rate first."""
    for key in sorted((k for k in gains if k[0] in terms), key=lambda k: (-k[1], k[0])):
        taken = min(gains[key], loss)
        gains[key] -= taken
        loss -= taken


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
    not_modelled = len(sales) - len(modelled)
    # FY -> term -> rate (-1 for the slab rate) -> net gain
    buckets: dict[str, dict[str, dict[float, float]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(float))
    )
    for sale in modelled:
        term, rate, indexed = _treatment(sale, tax_class)
        gain = _gain(sale, tax_class, indexed, nav_2018_01_31)
        buckets[_financial_year(sale.sold)][term][-1.0 if rate is None else rate] += gain
    years: list[dict[str, float | str]] = []
    total = 0.0
    for year in sorted(buckets):
        terms = buckets[year]
        if slab_rate is None and any(g > 0 for g in terms[SLAB].values()):
            return TaxResult(TAX_RULES, None, [], not_modelled, "slab_rate_needed")
        # (term, rate) -> positive gain; the slab rate stands in for -1.
        gains = {
            (term, (slab_rate or 0.0) if rate < 0 else rate): g
            for term, by_rate in terms.items()
            for rate, g in by_rate.items()
            if g > 0
        }
        losses = {t: -sum(g for g in terms[t].values() if g < 0) for t in (SHORT, LONG, SLAB)}
        _offset(gains, losses[LONG], (LONG,))
        _offset(gains, losses[SHORT] + losses[SLAB], (SHORT, LONG, SLAB))
        summed = {t: sum(g for (term, _), g in gains.items() if term == t) for t in terms}
        if tax_class == "equity":
            _offset(gains, 125_000.0 if int(year[2:6]) >= 2024 else 100_000.0, (LONG,))
        tax = sum(g * rate for (_, rate), g in gains.items()) * (1 + CESS)
        years.append(
            {
                "year": year,
                "short_term": summed.get(SHORT, 0.0),
                "long_term": summed.get(LONG, 0.0),
                "slab": summed.get(SLAB, 0.0),
                "tax": tax,
            }
        )
        total += tax
    return TaxResult(TAX_RULES, total, years, not_modelled)
