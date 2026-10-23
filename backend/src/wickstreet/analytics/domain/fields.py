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
    METHOD_VERSION,
    ROLLING,
    TRAILING,
    VOLATILITY,
    FundMetrics,
    Value,
)
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


def _period(months: int) -> str:
    return f"{months}M" if months < 12 else f"{months // 12}Y"


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


def row_values(fund: FundRecord, metrics: FundMetrics) -> tuple[Value, ...]:
    """Every field of one fund, in registry order."""
    category = classify.canonical_category(fund.category)
    option = classify.option_of(fund)
    attributes: dict[str, Value] = {
        "amc": fund.amc or "",
        "category": category,
        "source_category": fund.category or "",
        "asset_class": classify.asset_class(category),
        "scheme_type": fund.scheme_type or "",
        "plan": classify.plan_of(fund),
        "option": option,
        "return_basis": classify.return_basis(option),
    }
    values = attributes | metrics.values
    return tuple(values[field.id] for field in FIELDS)
