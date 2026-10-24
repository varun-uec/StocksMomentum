"""The screener field registry, generated from the v1 metric definitions (ADR-018).

A formula and its screen field cannot drift: each metric field comes from the
tables in :mod:`metrics`. ``registry_version`` changes with any field.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

from wickstreet.analytics.domain import classify
from wickstreet.analytics.domain.enrichment import FACT_FIELDS, IDCW_FIELDS
from wickstreet.analytics.domain.fieldspec import Field
from wickstreet.analytics.domain.holdings import HOLDING_FIELDS
from wickstreet.analytics.domain.metrics import (
    DRAWDOWN,
    EPISODES,
    METHOD_VERSION,
    ROLLING,
    STATUSES,
    TRAILING,
    VOLATILITY,
    WORST,
    Value,
)
from wickstreet.analytics.domain.peers import PEER_METRICS, SCORE_PARTS, THEN_METRICS
from wickstreet.analytics.domain.relations import NEAR_DUPLICATE
from wickstreet.mf_data.domain.reads import FundRecord

_FRACTION = "fraction"


CATEGORY_BASES = ("amfi", "scheme_sibling", "none")


def _period(months: int) -> str:
    return f"{months}M" if months < 12 else f"{months // 12}Y"


def _window(months: int | None) -> str:
    return "Since first NAV" if months is None else _period(months)


# The labels of the ranked base fields, so a derived field reads "Sharpe 3Y category
# rank", not "SHARPE 3Y category rank" (audit F-16).
_PEER_LABELS = {
    "ret_1y": "Return 1Y",
    "cagr_3y": "CAGR 3Y",
    "cagr_5y": "CAGR 5Y",
    "vol_3y": "Volatility 3Y",
    "mdd_3y": "Max drawdown 3Y",
    "sortino_3y": "Sortino 3Y",
    "sharpe_3y": "Sharpe 3Y",
    "ret_risk_3y": "Return per volatility 3Y",
    "consistency_3y": "Consistency 3Y",
    "score": "Score",
}


def _peer_label(name: str) -> str:
    return _PEER_LABELS[name]


_ROLLING_STATS = {
    "count": ("count", "number of rolling windows with a valid start", "count"),
    "mean": ("mean", "mean of the annualised rolling returns", _FRACTION),
    "median": ("median", "median of the annualised rolling returns", _FRACTION),
    "min": ("worst", "lowest annualised rolling return", _FRACTION),
    "max": ("best", "highest annualised rolling return", _FRACTION),
    "positive_share": ("positive share", "share of rolling returns above zero", _FRACTION),
    **{
        f"p{q}": (f"{q}th percentile", f"{q}th percentile (nearest rank) of the returns", _FRACTION)
        for q in (10, 25, 75, 90)
    },
}

FIELDS: tuple[Field, ...] = (
    Field("amc", "Fund house", "Fund", "enum", None, "AMC as AMFI's scheme master names it."),
    Field(
        "category",
        "Category",
        "Category",
        "enum",
        None,
        "AMFI's SEBI category; variant labels mapped only when they name one category.",
        (*classify.CATEGORIES, classify.UNCLASSIFIED),
    ),
    Field("source_category", "Source category", "Category", "enum", None, "Label as filed."),
    Field(
        "asset_class",
        "Asset class",
        "Category",
        "enum",
        None,
        "From the category prefix.",
        (
            "Equity",
            "Debt",
            "Hybrid",
            "Solution Oriented",
            "Life Cycle",
            "Other",
            classify.UNCLASSIFIED,
        ),
    ),
    Field(
        "fund_type",
        "Fund type",
        "Fund",
        "enum",
        None,
        "index, etf or fof from the category; otherwise open_ended, close_ended or interval "
        "from AMFI's scheme type.",
        classify.FUND_TYPES,
    ),
    Field("scheme_type", "Scheme type", "Fund", "enum", None, "Open, close or interval."),
    Field(
        "plan",
        "Plan",
        "Fund",
        "enum",
        None,
        "Direct when the plan or name says direct.",
        (classify.DIRECT, classify.REGULAR),
    ),
    Field(
        "option",
        "Option",
        "Fund",
        "enum",
        None,
        "From the plan-option text only, never the fund name.",
        classify.OPTIONS,
    ),
    Field(
        "return_basis",
        "Return basis",
        "Fund",
        "enum",
        None,
        "nav_excluding_payouts for every option but growth: " + classify.CAUTION,
        (classify.NAV_BASIS, classify.NAV_EXCLUDING_PAYOUTS),
    ),
    Field("active", "Active", "Fund", "boolean", None, "Last valid NAV within 7 days of as-of."),
    Field(
        "status",
        "Status",
        "Fund",
        "enum",
        None,
        "active (NAV within 7 days), historical (stopped publishing) or no_nav (no valid NAV).",
        STATUSES,
    ),
    Field(
        "category_basis",
        "Category basis",
        "Category",
        "enum",
        None,
        "amfi: the fund's own label; scheme_sibling: from the same scheme's other "
        "plan-options; none: Unclassified.",
        CATEGORY_BASES,
    ),
    Field("nav", "NAV", "Latest", "number", "INR", "Last valid NAV."),
    Field("last_nav_date", "Last NAV date", "Latest", "date", None, "Date of the last valid NAV."),
    Field(
        "excluded_navs", "Excluded NAVs", "Data", "number", "count", "Null, zero or negative rows."
    ),
    Field("jump_flags", "NAV jumps", "Data", "number", "count", "Rows kept but flagged nav_jump."),
    *(
        Field(
            name,
            f"{'CAGR' if annualised else 'Return'} {_period(months)}",
            "Returns",
            "number",
            _FRACTION,
            (
                f"(end/start)^(365.25/days) - 1 over {_period(months)}"
                if annualised
                else f"end/start - 1 over {_period(months)}"
            )
            + "; start is the last valid NAV within 7 days on or before the target date.",
        )
        for name, months, annualised in TRAILING
    ),
    Field(
        "since_start",
        "First valid NAV",
        "Returns",
        "date",
        None,
        "First stored valid NAV; not inception.",
    ),
    Field(
        "ret_since",
        "Return since first NAV",
        "Returns",
        "number",
        _FRACTION,
        "end/start - 1 from the first stored valid NAV; not since inception.",
    ),
    Field(
        "cagr_since",
        "CAGR since first NAV",
        "Returns",
        "number",
        _FRACTION,
        "Annualised from the first stored valid NAV; needs 365 days.",
    ),
    Field(
        "ret_ytd", "Return YTD", "Annual", "number", _FRACTION, "Since the last NAV of last year."
    ),
    Field(
        "ret_cy_last",
        "Return last calendar year",
        "Annual",
        "number",
        _FRACTION,
        "Year-end to year-end.",
    ),
    Field(
        "ret_fy_last",
        "Return last financial year",
        "Annual",
        "number",
        _FRACTION,
        "31 Mar to 31 Mar.",
    ),
    Field(
        "cy_best",
        "Best calendar year",
        "Annual",
        "number",
        _FRACTION,
        "Over complete stored years.",
    ),
    Field(
        "cy_worst",
        "Worst calendar year",
        "Annual",
        "number",
        _FRACTION,
        "Over complete stored years.",
    ),
    Field(
        "cy_positive_share",
        "Positive calendar years",
        "Annual",
        "number",
        _FRACTION,
        "Share of complete stored calendar years above zero.",
    ),
    Field("cy_count", "Calendar years", "Annual", "number", "count", "Complete stored years."),
    *(
        Field(
            name,
            f"Volatility {_period(months)}",
            "Risk",
            "number",
            _FRACTION,
            "Sample standard deviation of returns between consecutive NAVs, times √252.",
        )
        for name, months in VOLATILITY
    ),
    *(
        Field(
            name,
            f"Max drawdown {_period(months)}",
            "Risk",
            "number",
            _FRACTION,
            "Largest fall from a running peak; always <= 0.",
        )
        for name, months in DRAWDOWN
    ),
    Field(
        "mdd_since",
        "Max drawdown since first NAV",
        "Risk",
        "number",
        _FRACTION,
        "Largest fall from a running peak over the stored history.",
    ),
    *(
        field
        for name, months in EPISODES
        for field in (
            Field(
                f"{name}_peak",
                f"{_window(months)} drawdown peak",
                "Drawdown",
                "date",
                None,
                "NAV peak before the deepest fall.",
            ),
            Field(
                f"{name}_trough",
                f"{_window(months)} drawdown trough",
                "Drawdown",
                "date",
                None,
                "Lowest NAV of the deepest fall.",
            ),
            Field(
                f"{name}_recovery",
                f"{_window(months)} recovery date",
                "Drawdown",
                "date",
                None,
                "First NAV back at the peak; NA not_recovered otherwise.",
            ),
            Field(
                f"{name}_fall_days",
                f"{_window(months)} fall length",
                "Drawdown",
                "number",
                "days",
                "Calendar days from peak to trough.",
            ),
            Field(
                f"{name}_recovery_days",
                f"{_window(months)} recovery time",
                "Drawdown",
                "number",
                "days",
                "Calendar days from trough to recovery.",
            ),
        )
    ),
    *(
        Field(
            name,
            f"Worst {_period(months)}",
            "Risk",
            "number",
            _FRACTION,
            f"Lowest end/start - 1 over every {_period(months)} window in the stored history.",
        )
        for name, months in WORST
    ),
    Field(
        "downside_dev_3y",
        "Downside deviation 3Y",
        "Risk",
        "number",
        _FRACTION,
        "Root mean square of daily returns below 0%, times √252.",
    ),
    Field(
        "sortino_3y",
        "Sortino 3Y",
        "Risk",
        "number",
        "ratio",
        "(CAGR 3Y − risk-free 3Y) ÷ downside deviation below the risk-free return of each "
        "interval (RBI 91-day T-bill).",
    ),
    Field(
        "var95_3y",
        "VaR 95% 1-day 3Y",
        "Risk",
        "number",
        _FRACTION,
        "5th-percentile daily return over 3Y (historical, nearest rank).",
    ),
    Field(
        "cvar95_3y",
        "CVaR 95% 1-day 3Y",
        "Risk",
        "number",
        _FRACTION,
        "Mean of daily returns at or below the 3Y VaR.",
    ),
    Field(
        "ret_risk_3y",
        "Return per volatility 3Y",
        "Risk",
        "number",
        "ratio",
        "CAGR 3Y ÷ volatility 3Y; not a Sharpe ratio (no risk-free rate).",
    ),
    Field(
        "rf_1y",
        "Risk-free 1Y",
        "Risk-free",
        "number",
        _FRACTION,
        "Annualised return of a deposit earning the RBI 91-day T-bill cut-off yield each "
        "day, over the fund's 1Y window. Source: Reserve Bank of India.",
    ),
    Field(
        "rf_3y",
        "Risk-free 3Y",
        "Risk-free",
        "number",
        _FRACTION,
        "As Risk-free 1Y, over the fund's 3Y window. Source: Reserve Bank of India.",
    ),
    Field(
        "sharpe_1y",
        "Sharpe 1Y",
        "Risk-free",
        "number",
        "ratio",
        "(Return 1Y − risk-free 1Y) ÷ volatility 1Y.",
    ),
    Field(
        "sharpe_3y",
        "Sharpe 3Y",
        "Risk-free",
        "number",
        "ratio",
        "(CAGR 3Y − risk-free 3Y) ÷ volatility 3Y.",
    ),
    Field(
        "dd_now",
        "Current drawdown",
        "Drawdown",
        "number",
        _FRACTION,
        "Last NAV ÷ highest NAV so far - 1; active funds only.",
    ),
    Field(
        "dd_now_days",
        "Days since peak",
        "Drawdown",
        "number",
        "days",
        "Calendar days since the last NAV at the running peak; active funds only.",
    ),
    Field(
        "underwater_max_days",
        "Longest time under water",
        "Drawdown",
        "number",
        "days",
        "Longest stretch below a peak in the stored history, recovered or not.",
    ),
    Field(
        "consistency_3y",
        "Consistency 3Y",
        "Peers",
        "number",
        _FRACTION,
        "Share of month-ends whose rolling 3Y return beat the median of the peers alive that "
        "month, including funds that later stopped.",
    ),
    Field(
        "q1_share_3y",
        "Top-quartile share 3Y",
        "Persistence",
        "number",
        _FRACTION,
        "Share of the last 36 month-ends with the 1Y return in the top quartile of the peers "
        "alive then; needs 12 ranked month-ends.",
    ),
    Field(
        "pct_mean_3y",
        "Mean percentile 3Y",
        "Persistence",
        "number",
        "percentile",
        "Mean point-in-time category percentile of the 1Y return over the last 36 month-ends.",
    ),
    *(
        Field(
            f"{name}_cat_pct_1y_ago",
            f"{_peer_label(name)} percentile 1Y ago",
            "Deterioration",
            "number",
            "percentile",
            "Category percentile one year before as-of, among the peers alive then.",
        )
        for name, _ in THEN_METRICS
    ),
    Field(
        "ret_1y_cat_quartile_1y_ago",
        "Return 1Y quartile 1Y ago",
        "Deterioration",
        "number",
        "quartile",
        "Category quartile of the 1Y return one year before as-of.",
    ),
    *(
        Field(
            f"{name}_pct_chg_1y",
            f"{_peer_label(name)} percentile change 1Y",
            "Deterioration",
            "number",
            "percentile",
            "Category percentile now minus one year ago; negative = fell behind peers.",
        )
        for name, _ in THEN_METRICS
    ),
    Field(
        "quartile_change_1y",
        "Return 1Y quartile change",
        "Deterioration",
        "number",
        "quartile",
        "Quartile one year ago minus quartile now; negative = moved down.",
    ),
    Field(
        "consistency_3y_chg_1y",
        "Consistency change 1Y",
        "Deterioration",
        "number",
        _FRACTION,
        "Consistency 3Y now minus consistency 3Y as it stood 12 month-ends earlier.",
    ),
    Field(
        "dr_gap_1y",
        "Direct–regular gap 1Y",
        "Direct vs regular",
        "number",
        _FRACTION,
        "Direct plan 1Y return minus regular plan 1Y return, same scheme and option. "
        "Observed NAV gap, not TER.",
    ),
    Field(
        "dr_gap_3y",
        "Direct–regular gap 3Y",
        "Direct vs regular",
        "number",
        _FRACTION,
        "Direct plan 3Y CAGR minus regular plan 3Y CAGR. Observed NAV gap, not TER.",
    ),
    Field(
        "dr_wealth_10y",
        "Direct–regular wealth gap",
        "Direct vs regular",
        "number",
        "INR",
        "₹10 lakh over 10 years at each plan's 3Y CAGR: direct value minus regular value.",
    ),
    Field(
        "near_duplicates",
        "Near-duplicates",
        "Correlation",
        "number",
        "count",
        f"Active peers whose daily returns over 3Y correlate at {NEAR_DUPLICATE} or more "
        "(500 common days minimum).",
    ),
    *(
        field
        for name, higher in PEER_METRICS
        for field in (
            Field(
                f"{name}_cat_rank",
                f"{_peer_label(name)} category rank",
                "Peers",
                "number",
                "rank",
                f"1 = best ({'highest' if higher else 'lowest'}) among active peers.",
            ),
            Field(
                f"{name}_cat_pct",
                f"{_peer_label(name)} category percentile",
                "Peers",
                "number",
                "percentile",
                "100 = best; ties share the average rank.",
            ),
            Field(
                f"{name}_cat_quartile",
                f"{_peer_label(name)} category quartile",
                "Peers",
                "number",
                "quartile",
                "1 = top quarter.",
            ),
            Field(
                f"{name}_cat_count",
                f"{_peer_label(name)} peers ranked",
                "Peers",
                "number",
                "count",
                "Active peers with a value; ranks need 5.",
            ),
            Field(
                f"{name}_cat_median",
                f"{_peer_label(name)} category median",
                "Peers",
                "number",
                None,
                "Median over the ranked peers.",
            ),
        )
    ),
    Field(
        "score",
        "Score",
        "Peers",
        "number",
        "percentile",
        "Equal-weight mean of the category percentiles of " + ", ".join(SCORE_PARTS) + ".",
    ),
    *(
        Field(
            f"{name}_{stat}",
            f"Rolling {_period(months)} {label}",
            "Rolling",
            "number",
            unit,
            f"{description.capitalize()}, {_period(months)} windows over the stored history.",
        )
        for name, months in ROLLING
        for stat, (label, description, unit) in _ROLLING_STATS.items()
    ),
    *FACT_FIELDS,
    *IDCW_FIELDS,
    *HOLDING_FIELDS,
)
BY_ID = {field.id: field for field in FIELDS}
INDEX = {field.id: i for i, field in enumerate(FIELDS)}


def registry_version() -> str:
    """SHA-256 of the method version and every field definition."""
    body = json.dumps(
        {"method_version": METHOD_VERSION, "fields": [asdict(f) for f in FIELDS]}, sort_keys=True
    )
    return hashlib.sha256(body.encode()).hexdigest()


def attributes(fund: FundRecord, sibling: str | None) -> dict[str, Value]:
    """The classification fields of one fund; ``sibling`` is a category from its scheme."""
    category = classify.canonical_category(fund.category)
    basis = "amfi" if category != classify.UNCLASSIFIED else "scheme_sibling" if sibling else "none"
    category = sibling or category
    option = classify.option_of(fund)
    return {
        "amc": fund.amc or "",
        "category": category,
        "category_basis": basis,
        "source_category": fund.category or "",
        "asset_class": classify.asset_class(category),
        "scheme_type": fund.scheme_type or "",
        "fund_type": classify.fund_type(category, fund.scheme_type),
        "plan": classify.plan_of(fund),
        "option": option,
        "return_basis": classify.return_basis(option),
    }


def ordered(values: dict[str, Value]) -> tuple[Value, ...]:
    """Every field of one fund, in registry order."""
    return tuple(values[field.id] for field in FIELDS)
