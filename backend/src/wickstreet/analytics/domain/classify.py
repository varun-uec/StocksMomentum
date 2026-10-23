"""Methodology v1: plan, option and category of a plan-option (ADR-017 MF-8).

The option comes from the plan-option text only, never from the fund name, so
"X Dividend Yield Fund - Growth" is a growth option. Categories are AMFI's SEBI
labels as AMFI writes them: the 2017 framework, plus the labels of SEBI's revised
framework (circular of 26 February 2026) that name no 2017 category (method v4).
A variant label maps only when it names exactly one of them; every other label is
``Unclassified``. Each mapping is listed here and in
``docs/current/mf-metrics.md``; changing one bumps ``METHOD_VERSION``.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence

from wickstreet.mf_data.domain.reads import FundRecord

DIRECT, REGULAR = "direct", "regular"
IDCW, BONUS, GROWTH, UNKNOWN = "idcw", "bonus", "growth", "unknown"
OPTIONS = (GROWTH, IDCW, BONUS, UNKNOWN)
NAV_BASIS, NAV_EXCLUDING_PAYOUTS = "nav", "nav_excluding_payouts"
CAUTION = "NAV return; excludes payouts; not a total return."
UNCLASSIFIED = "Unclassified"

# Phrases of fund and plan names, removed before the option words are matched:
# "Dividend Yield" (renamed "IDCW Yield" by AMFI), "Growth Fund", and the unclaimed
# dividend plans, whose options are growth options.
_FUND_PHRASES = re.compile(
    r"(?:dividend|idcw) (?:yield|opportunit\w*)|growth (?:fund|opportunit\w*|&|and)"
    r"|income fund|unclaimed[^-]*?\b(?:dividend|idcw|div)\b",
    re.IGNORECASE,
)
# "idwc" is a misspelling AMFI files carry.
_IDCW_WORDS = re.compile(
    r"idcw|idwc|dividend|\bdiv\b|payout|\breinvest|income distribution", re.IGNORECASE
)
_BONUS_WORDS = re.compile(r"\bbonus\b", re.IGNORECASE)
_GROWTH_WORDS = re.compile(r"growth|cumulative", re.IGNORECASE)
_DIRECT_WORD = re.compile(r"\bdirect\b", re.IGNORECASE)

_ASSET_CLASSES = {
    "Equity Scheme - ": "Equity",
    "Debt Scheme - ": "Debt",
    "Hybrid Scheme - ": "Hybrid",
    "Solution Oriented Scheme - ": "Solution Oriented",
    "Other Scheme - ": "Other",
    "Income/Debt Oriented Schemes - ": "Debt",
    "Life Cycle Funds - ": "Life Cycle",
}
CATEGORIES = tuple(
    prefix + name
    for prefix, names in (
        (
            "Equity Scheme - ",
            (
                "Large Cap Fund",
                "Large & Mid Cap Fund",
                "Mid Cap Fund",
                "Small Cap Fund",
                "Multi Cap Fund",
                "Flexi Cap Fund",
                "Focused Fund",
                "Value Fund",
                "Contra Fund",
                "Dividend Yield Fund",
                "ELSS",
                "Sectoral/ Thematic",
            ),
        ),
        (
            "Debt Scheme - ",
            (
                "Overnight Fund",
                "Liquid Fund",
                "Ultra Short Duration Fund",
                "Low Duration Fund",
                "Money Market Fund",
                "Short Duration Fund",
                "Medium Duration Fund",
                "Medium to Long Duration Fund",
                "Long Duration Fund",
                "Dynamic Bond",
                "Corporate Bond Fund",
                "Credit Risk Fund",
                "Banking and PSU Fund",
                "Gilt Fund",
                "Gilt Fund with 10 year constant duration",
                "Floater Fund",
            ),
        ),
        (
            "Hybrid Scheme - ",
            (
                "Conservative Hybrid Fund",
                "Balanced Hybrid Fund",
                "Aggressive Hybrid Fund",
                "Dynamic Asset Allocation or Balanced Advantage",
                "Multi Asset Allocation",
                "Arbitrage Fund",
                "Equity Savings",
            ),
        ),
        ("Solution Oriented Scheme - ", ("Retirement Fund", "Children s Fund")),
        (
            "Other Scheme - ",
            ("Index Funds", "Other  ETFs", "Gold ETF", "FoF Overseas", "FoF Domestic"),
        ),
    )
    for name in names
)
_INCOME = "Income/Debt Oriented Schemes - "
# SEBI's 2026 framework, as AMFI writes it, where no 2017 category has the same name.
# They are their own peer groups: mapping "Short Term" to "Short Duration" would guess.
CATEGORIES_2026 = (
    *(
        _INCOME + name
        for name in (
            "Ultra Short Term Fund",
            "Ultra Short to Short Term Fund",
            "Short Term Fund",
            "Medium Term Fund",
            "Medium to Long Term Fund",
            "Long Term Fund",
            "Dynamic Term Fund",
            "Sectoral Fund",
        )
    ),
    # SEBI allows maturities of 5 to 30 years in steps of 5.
    *(f"Life Cycle Funds - Life Cycle Fund with Maturity of {n} Years" for n in range(5, 31, 5)),
)
CATEGORIES = (*CATEGORIES, *CATEGORIES_2026)
_CANONICAL = frozenset(CATEGORIES)


def _same(prefix: str, canonical_prefix: str, names: tuple[str, ...]) -> dict[str, str]:
    return {prefix + name: canonical_prefix + name for name in names}


_E, _D, _H = "Equity Scheme - ", "Debt Scheme - ", "Hybrid Scheme - "
_ETF = "Exchange Traded Funds (ETFs) - "
# Variant label -> the one canonical label it names. Broad labels (Income, Growth,
# Balanced, Gilt) name no single category, so they stay Unclassified.
ALIASES: dict[str, str] = {
    **_same(
        "Equity Schemes - ",
        _E,
        (
            "Large Cap Fund",
            "Large & Mid Cap Fund",
            "Mid Cap Fund",
            "Small Cap Fund",
            "Multi Cap Fund",
            "Flexi Cap Fund",
            "Focused Fund",
            "Value Fund",
            "Contra Fund",
            "Dividend Yield Fund",
        ),
    ),
    "Equity Schemes - ELSS- Tax Saver Fund": _E + "ELSS",
    "ELSS": _E + "ELSS",
    "Equity Schemes - Sectoral Fund": _E + "Sectoral/ Thematic",
    "Equity Schemes - Thematic Fund": _E + "Sectoral/ Thematic",
    **_same(
        _INCOME,
        _D,
        ("Overnight Fund", "Liquid Fund", "Money Market Fund", "Corporate Bond Fund"),
    ),
    _INCOME + "Credit Risk Fund": _D + "Credit Risk Fund",
    _INCOME + "Gilt Fund": _D + "Gilt Fund",
    _INCOME + "Banking and PSU Debt Fund": _D + "Banking and PSU Fund",
    _INCOME + "10-year Constant Maturity Gilt Fund": _D
    + "Gilt Fund with 10 year constant duration",
    _INCOME + "Floating Interest Rates Fund": _D + "Floater Fund",
    "Liquid": _D + "Liquid Fund",
    "Money Market": _D + "Money Market Fund",
    "Floating Rate": _D + "Floater Fund",
    **_same(
        "Hybrid Schemes - ",
        _H,
        (
            "Aggressive Hybrid Fund",
            "Conservative Hybrid Fund",
            "Balanced Hybrid Fund",
            "Arbitrage Fund",
        ),
    ),
    "Hybrid Schemes - Multi Asset Allocation Fund": _H + "Multi Asset Allocation",
    "Hybrid Schemes - Equity Savings Fund": _H + "Equity Savings",
    "Hybrid Schemes - Balanced Advantage Fund/ Dynamic Asset Allocation": (
        _H + "Dynamic Asset Allocation or Balanced Advantage"
    ),
    "Solution Oriented Schemes ** - Retirement Fund": "Solution Oriented Scheme - Retirement Fund",
    "Children s Fund - Childrens' Fund": "Solution Oriented Scheme - Children s Fund",
    "Solution Oriented Scheme - Childrenâ€™s Fund": "Solution Oriented Scheme - Children s Fund",
    "Index Funds - Equity Funds": "Other Scheme - Index Funds",
    "Index Funds - Debt Funds": "Other Scheme - Index Funds",
    "Index Funds - Hybrid Fund": "Other Scheme - Index Funds",
    "Fund of Funds Scheme (Domestic) - Fund of Funds Scheme (Domestic)": (
        "Other Scheme - FoF Domestic"
    ),
    "Fund of Funds - Domestic": "Other Scheme - FoF Domestic",
    "Overseas Fund of Funds - Fund of Funds investing overseas": "Other Scheme - FoF Overseas",
    "Fund of Funds - Overseas": "Other Scheme - FoF Overseas",
    _ETF + "Gold ETF": "Other Scheme - Gold ETF",
    "GOLD ETFs": "Other Scheme - Gold ETF",
    **{
        _ETF + kind: "Other Scheme - Other  ETFs"
        for kind in (
            "Equity ETF",
            "Debt ETF",
            "Other ETF",
            "Silver ETF",
            "ETFs investing overseas",
            "Hybrid ETF",
        )
    },
    "Other ETFs": "Other Scheme - Other  ETFs",
}


def canonical_category(label: str | None) -> str:
    """AMFI's SEBI label for ``label``, or ``Unclassified``."""
    if label is None:
        return UNCLASSIFIED
    label = label.strip()
    if label in _CANONICAL:
        return label
    return ALIASES.get(label, UNCLASSIFIED)


def asset_class(category: str) -> str:
    """Equity, Debt, Hybrid, Solution Oriented, Other or Unclassified."""
    return next(
        (name for prefix, name in _ASSET_CLASSES.items() if category.startswith(prefix)),
        UNCLASSIFIED,
    )


OPEN_ENDED, CLOSE_ENDED, INTERVAL = "open_ended", "close_ended", "interval"
INDEX_FUND, ETF, FOF = "index", "etf", "fof"
FUND_TYPES = (OPEN_ENDED, CLOSE_ENDED, INTERVAL, INDEX_FUND, ETF, FOF)
_TYPE_OF_CATEGORY = {
    "Other Scheme - Index Funds": INDEX_FUND,
    "Other Scheme - Gold ETF": ETF,
    "Other Scheme - Other  ETFs": ETF,
    "Other Scheme - FoF Overseas": FOF,
    "Other Scheme - FoF Domestic": FOF,
}


def fund_type(category: str, scheme_type: str | None) -> str:
    """Index fund, ETF or fund of funds by category; otherwise open, close or interval.

    AMFI writes the scheme type as "Open Ended", "Close Ended Schemes", "Interval Fund"
    and so on; an unrecognised one counts as open ended.
    """
    if category in _TYPE_OF_CATEGORY:
        return _TYPE_OF_CATEGORY[category]
    kind = (scheme_type or "").lower()
    return (
        CLOSE_ENDED if kind.startswith("close") else INTERVAL if "interval" in kind else OPEN_ENDED
    )


def option_text(fund: FundRecord) -> str:
    """The plan-option part of the name: AMFI's option column, else the name less the scheme."""
    if fund.option:
        return fund.option
    name = fund.nav_name or ""
    scheme = fund.scheme_name or ""
    if scheme and len(name) > len(scheme) and name.lower().startswith(scheme.lower()):
        return name[len(scheme) :]
    return name


def option_of(fund: FundRecord) -> str:
    """``idcw``, ``bonus``, ``growth`` or ``unknown``, in that order of precedence."""
    text = _FUND_PHRASES.sub(" ", option_text(fund))
    if _IDCW_WORDS.search(text):
        return IDCW
    if _BONUS_WORDS.search(text):
        return BONUS
    if _GROWTH_WORDS.search(text):
        return GROWTH
    return UNKNOWN


def plan_of(fund: FundRecord) -> str:
    """``direct`` when the plan column or the name says so, else ``regular``."""
    return DIRECT if _DIRECT_WORD.search(f"{fund.plan or ''} {fund.nav_name or ''}") else REGULAR


def return_basis(option: str) -> str:
    """Only a growth option's NAV return is its whole return."""
    return NAV_BASIS if option == GROWTH else NAV_EXCLUDING_PAYOUTS


def sibling_categories(funds: Sequence[FundRecord]) -> dict[int, str]:
    """Categories for Unclassified plan-options, taken from their own scheme (method v3).

    A plan-option whose label maps to no category takes the canonical category of the
    other plan-options of the same scheme (same AMC and scheme name), when they name
    exactly one. Returns plan-option id -> category for the ones it resolves.
    """
    by_scheme: dict[tuple[str, str], set[str]] = defaultdict(set)
    for fund in funds:
        if fund.amc and fund.scheme_name:
            category = canonical_category(fund.category)
            if category != UNCLASSIFIED:
                by_scheme[(fund.amc, fund.scheme_name)].add(category)
    resolved: dict[int, str] = {}
    for fund in funds:
        if canonical_category(fund.category) == UNCLASSIFIED and fund.amc and fund.scheme_name:
            found = by_scheme.get((fund.amc, fund.scheme_name), set())
            if len(found) == 1:
                resolved[fund.plan_option_id] = next(iter(found))
    return resolved
