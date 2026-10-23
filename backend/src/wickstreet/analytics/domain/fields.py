"""The screener field registry, generated from the v1 metric definitions (ADR-018).

A formula and its screen field cannot drift: each metric field comes from the
tables in :mod:`metrics`. ``registry_version`` changes with any field.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Literal

from wickstreet.analytics.domain import classify
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
from wickstreet.analytics.domain.peers import PEER_METRICS, SCORE_PARTS
from wickstreet.mf_data.domain.reads import FundRecord

FieldType = Literal["number", "boolean", "enum", "date"]
_FRACTION = "fraction"


@dataclass(frozen=True, slots=True)
class Field:
    """One screenable value. ``values`` lists an enum's members; ``None`` means the snapshot's."""

    id: str
    label: str
    group: str
    type: FieldType
    unit: str | None
    description: str
    values: tuple[str, ...] | None = None


CATEGORY_BASES = ("amfi", "scheme_sibling", "none")


def _period(months: int) -> str:
    return f"{months}M" if months < 12 else f"{months // 12}Y"


def _window(months: int | None) -> str:
    return "Since first NAV" if months is None else _period(months)


def _peer_label(name: str) -> str:
    return "Score" if name == "score" else name.replace("_", " ").upper()


_ROLLING_STATS = {
    "count": ("count", "number of rolling windows with a valid start", "count"),
    "mean": ("mean", "mean of the annualised rolling returns", _FRACTION),
    "median": ("median", "median of the annualised rolling returns", _FRACTION),
    "min": ("worst", "lowest annualised rolling return", _FRACTION),
    "max": ("best", "highest annualised rolling return", _FRACTION),
    "positive_share": ("positive share", "share of rolling returns above zero", _FRACTION),
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
        ("Equity", "Debt", "Hybrid", "Solution Oriented", "Other", classify.UNCLASSIFIED),
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
        "CAGR 3Y ÷ downside deviation 3Y; threshold 0% until a risk-free series is stored.",
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
        "consistency_3y",
        "Consistency 3Y",
        "Peers",
        "number",
        _FRACTION,
        "Share of month-ends whose rolling 3Y return beat the category median that month.",
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
        "plan": classify.plan_of(fund),
        "option": option,
        "return_basis": classify.return_basis(option),
    }


def ordered(values: dict[str, Value]) -> tuple[Value, ...]:
    """Every field of one fund, in registry order."""
    return tuple(values[field.id] for field in FIELDS)
