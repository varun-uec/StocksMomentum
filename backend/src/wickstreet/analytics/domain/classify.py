"""Methodology v1: plan, option and category of a plan-option (ADR-017 MF-8).

The option comes from the plan-option text only, never from the fund name, so
"X Dividend Yield Fund - Growth" is a growth option. Categories are AMFI's SEBI
labels as AMFI writes them. A variant label maps only when it names exactly one of
them; every other label is ``Unclassified``. Each mapping is listed here and in
``docs/current/mf-metrics.md``; changing one bumps ``METHOD_VERSION``.
"""

from __future__ import annotations

import re

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
_CANONICAL = frozenset(CATEGORIES)


def _same(prefix: str, canonical_prefix: str, names: tuple[str, ...]) -> dict[str, str]:
    return {prefix + name: canonical_prefix + name for name in names}


_E, _D, _H = "Equity Scheme - ", "Debt Scheme - ", "Hybrid Scheme - "
_INCOME = "Income/Debt Oriented Schemes - "
_ETF = "Exchange Traded Funds (ETFs) - "
# Variant label -> the one canonical label it names. Old pre-2018 debt terms
# (Short Term, Ultra Short Term, Dynamic Term ...) and broad labels (Income, Growth,
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
