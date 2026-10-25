"""Prebuilt screens (doc 06 §5): each is an ordinary filter, sort and column set."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_DIRECT_GROWTH: list[dict[str, Any]] = [
    {"field": "status", "op": "in", "value": ["active"]},
    {"field": "plan", "op": "in", "value": ["direct"]},
    {"field": "option", "op": "in", "value": ["growth"]},
]

# Every SEBI equity category but Sectoral/Thematic: one sector or theme is not diversified.
_DIVERSIFIED_EQUITY = [
    "Equity Scheme - Large Cap Fund",
    "Equity Scheme - Large & Mid Cap Fund",
    "Equity Scheme - Mid Cap Fund",
    "Equity Scheme - Small Cap Fund",
    "Equity Scheme - Multi Cap Fund",
    "Equity Scheme - Flexi Cap Fund",
    "Equity Scheme - Focused Fund",
    "Equity Scheme - Value Fund",
    "Equity Scheme - Contra Fund",
    "Equity Scheme - Dividend Yield Fund",
    "Equity Scheme - ELSS",
]


@dataclass(frozen=True, slots=True)
class Preset:
    """A named screen and the one-line purpose it serves."""

    id: str
    name: str
    purpose: str
    filter: dict[str, Any]
    sort: list[dict[str, str]]
    columns: list[str]


PRESETS = (
    Preset(
        "category_leaders",
        "Category leaders",
        "The three best-scored direct growth funds in each category.",
        {"all": [*_DIRECT_GROWTH, {"field": "score_cat_rank", "op": "<=", "value": 3}]},
        [{"field": "category", "dir": "asc"}, {"field": "score", "dir": "desc"}],
        ["category", "score", "score_cat_rank", "consistency_3y", "cagr_3y", "mdd_3y"],
    ),
    Preset(
        "consistent_large_caps",
        "Consistent large caps",
        "Large-cap funds whose rolling 3Y return beat the category median in 70% of months.",
        {
            "all": [
                *_DIRECT_GROWTH,
                {"field": "category", "op": "in", "value": ["Equity Scheme - Large Cap Fund"]},
                {"field": "consistency_3y", "op": ">=", "value": 0.7},
            ]
        },
        [{"field": "consistency_3y", "dir": "desc"}],
        ["consistency_3y", "cagr_3y", "cagr_5y", "vol_3y", "mdd_3y"],
    ),
    Preset(
        "calm_equity",
        "Calm equity by category",
        "Diversified equity funds, no sector or theme funds, in the calmer half of their "
        "category by 3Y volatility, with a 3Y return at or above the category median. "
        "Calmest first.",
        {
            "all": [
                *_DIRECT_GROWTH,
                {"field": "category", "op": "in", "value": _DIVERSIFIED_EQUITY},
                {"field": "vol_3y_cat_pct", "op": ">=", "value": 50},
                {"field": "cagr_3y_cat_pct", "op": ">=", "value": 50},
            ]
        },
        [{"field": "vol_3y", "dir": "asc"}],
        ["category", "vol_3y", "mdd_3y", "cagr_3y", "ret_risk_3y"],
    ),
    Preset(
        "shallow_drawdown_hybrids",
        "Shallow-drawdown hybrids",
        "Hybrid funds whose worst 3Y fall was no deeper than 15%.",
        {
            "all": [
                *_DIRECT_GROWTH,
                {"field": "asset_class", "op": "in", "value": ["Hybrid"]},
                {"field": "mdd_3y", "op": ">=", "value": -0.15},
            ]
        },
        [{"field": "cagr_3y", "dir": "desc"}],
        ["category", "mdd_3y", "cagr_3y", "vol_3y"],
    ),
    Preset(
        "steady_debt",
        "Steady debt",
        "Debt funds with low volatility and no negative 1Y window in their stored history.",
        {
            "all": [
                *_DIRECT_GROWTH,
                {"field": "asset_class", "op": "in", "value": ["Debt"]},
                {"field": "vol_3y", "op": "<=", "value": 0.02},
                {"field": "worst_1y", "op": ">=", "value": 0},
            ]
        },
        [{"field": "cagr_3y", "dir": "desc"}],
        ["category", "cagr_3y", "vol_3y", "worst_1y"],
    ),
    Preset(
        "ten_year_compounders",
        "Ten-year compounders",
        "Positive in 80% of calendar years and in the top quarter of all funds by 10Y CAGR.",
        {
            "all": [
                *_DIRECT_GROWTH,
                {"field": "cy_positive_share", "op": ">=", "value": 0.8},
                {"field": "cagr_10y", "op": "top_pct", "value": 25},
            ]
        },
        [{"field": "cagr_10y", "dir": "desc"}],
        ["category", "cagr_10y", "cy_positive_share", "cy_worst", "mdd_since"],
    ),
)
