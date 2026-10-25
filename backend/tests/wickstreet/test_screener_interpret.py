"""Plain-language screens: each phrase becomes a stated, runnable condition."""

from __future__ import annotations

import pytest

from wickstreet.analytics.domain.interpret import interpret
from wickstreet.analytics.domain.presets import DIVERSIFIED_EQUITY
from wickstreet.analytics.domain.screening import parse_filter

DEFAULTS = [
    {"field": "status", "op": "in", "value": ["active"]},
    {"field": "plan", "op": "in", "value": ["direct"]},
    {"field": "option", "op": "in", "value": ["growth"]},
]


def test_the_mission_request_reads_into_four_stated_conditions() -> None:
    result = interpret(
        "Show me diversified equity funds with consistent five-year performance, "
        "relatively low drawdowns and TER below 1%."
    )
    assert result.filter == {
        "all": [
            *DEFAULTS,
            {"field": "category", "op": "in", "value": list(DIVERSIFIED_EQUITY)},
            {"field": "consistency_3y", "op": ">=", "value": 0.6},
            {"field": "cagr_5y_cat_pct", "op": ">=", "value": 50},
            {"field": "mdd_3y_cat_pct", "op": ">=", "value": 50},
            {"field": "ter", "op": "<", "value": 0.01},
        ]
    }
    assert [c.phrase for c in result.clauses] == [
        "diversified equity",
        "consistent five-year performance",
        "low drawdowns",
        "TER below 1%",
    ]
    assert result.not_understood == []
    assert len(result.assumptions) == 3
    assert result.columns[:5] == ["category", "consistency_3y", "cagr_5y", "mdd_3y", "ter"]


@pytest.mark.parametrize(
    ("text", "condition"),
    [
        ("TER under 0.75%", {"field": "ter", "op": "<", "value": 0.0075}),
        ("under 0.3% TER", {"field": "ter", "op": "<", "value": 0.003}),
        ("expense ratio at most 1.5%", {"field": "ter", "op": "<=", "value": 0.015}),
        ("returns above 12% over 5 years", {"field": "cagr_5y", "op": ">", "value": 0.12}),
        ("1 year return over 10%", {"field": "ret_1y", "op": ">", "value": 0.1}),
        ("AUM above 5000 crore", {"field": "aum_cr", "op": ">", "value": 5000.0}),
        ("AUM over 10k crore", {"field": "aum_cr", "op": ">", "value": 10000.0}),
        ("Sharpe above 1", {"field": "sharpe_3y", "op": ">", "value": 1.0}),
        ("drawdown less than 20%", {"field": "mdd_3y", "op": ">", "value": -0.2}),
        ("beat their benchmark over 5 years", {"field": "excess_5y", "op": ">", "value": 0}),
        ("low volatility", {"field": "vol_3y_cat_pct", "op": ">=", "value": 50}),
        ("low-cost", {"field": "ter_cat_pct", "op": ">=", "value": 50}),
        ("low risk", {"field": "riskometer_level", "op": "<=", "value": 3}),
    ],
)
def test_each_phrase_has_one_reading(text: str, condition: dict[str, object]) -> None:
    result = interpret(text)
    assert result.filter["all"][-1] == condition
    assert result.not_understood == []


def test_fund_houses_resolve_to_canonical_names_and_brands() -> None:
    result = interpret("ICICI and Kotak flexi cap funds, plus Parag Parikh")
    amc = next(c for c in result.filter["all"] if c["field"] == "amc")
    assert set(amc["value"]) == {
        "PPFAS Mutual Fund",
        "ICICI Prudential Mutual Fund",
        "Kotak Mahindra Mutual Fund",
    }
    # An ordinary word never names a house.
    assert all(c["field"] != "amc" for c in interpret("funds I can trust").filter["all"])


def test_unknown_words_are_reported_not_guessed() -> None:
    result = interpret("funds my uncle likes")
    assert result.filter == {"all": DEFAULTS}
    assert result.not_understood == ["my uncle likes"]
    assert result.notes


def test_a_sort_request_does_not_filter() -> None:
    result = interpret("liquid funds sorted by lowest TER")
    assert result.sort == [{"field": "ter", "dir": "asc"}]
    assert all(c["field"] not in ("ter", "ter_cat_pct") for c in result.filter["all"])


def test_a_capped_index_fund_request_says_the_index_is_not_a_field() -> None:
    result = interpret("large cap index funds")
    assert {
        "field": "category",
        "op": "in",
        "value": ["Other Scheme - Index Funds"],
    } in result.filter["all"]
    assert "not a screen field" in result.clauses[0].explanation


def test_a_refinement_replaces_and_removes_only_what_it_names() -> None:
    first = interpret("flexi cap funds with low drawdowns and TER below 1%")
    second = interpret(
        "TER below 0.8% and remove the drawdown limit", first.filter["all"], first.sort
    )
    assert second.refined
    assert second.filter == {
        "all": [
            *DEFAULTS,
            {"field": "category", "op": "in", "value": ["Equity Scheme - Flexi Cap Fund"]},
            {"field": "ter", "op": "<", "value": 0.008},
        ]
    }
    third = interpret("regular plans, any category", second.filter["all"])
    fields = [c["field"] for c in third.filter["all"]]
    assert "category" not in fields
    assert {"field": "plan", "op": "in", "value": ["regular"]} in third.filter["all"]
    assert fields.count("plan") == 1


@pytest.mark.parametrize(
    "text",
    [
        "best performing small cap funds over 3 years with AUM above 5000 crore",
        "low-cost ELSS with Sharpe above 1, regular plan, sorted by highest sharpe",
        "highly rated hybrid funds that beat the index",
        "calm large & mid cap IDCW funds from HDFC",
        "",
        "%%% 12 above",
    ],
)
def test_every_reading_is_a_runnable_screen(text: str) -> None:
    result = interpret(text or "funds")
    assert parse_filter(result.filter) is not None


SECTORAL = "Equity Scheme - Sectoral/ Thematic"


@pytest.mark.parametrize(
    ("text", "added"),
    [
        # A period is never a threshold (review finding 1).
        (
            "consistent returns over 5 years",
            [
                {"field": "consistency_3y", "op": ">=", "value": 0.6},
                {"field": "cagr_5y_cat_pct", "op": ">=", "value": 50},
            ],
        ),
        ("returns over 5 years above 15%", [{"field": "cagr_5y", "op": ">", "value": 0.15}]),
        (
            "returns at least 15% p.a. over 3 years",
            [{"field": "cagr_3y", "op": ">=", "value": 0.15}],
        ),
        # A negated category is excluded, not selected (2).
        ("not ELSS", [{"field": "category", "op": "not_in", "value": ["Equity Scheme - ELSS"]}]),
        (
            "flexi cap funds not sectoral",
            [{"field": "category", "op": "in", "value": ["Equity Scheme - Flexi Cap Fund"]}],
        ),
        (
            "equity funds without sectoral funds",
            [
                {"field": "asset_class", "op": "in", "value": ["Equity"]},
                {"field": "category", "op": "not_in", "value": [SECTORAL]},
            ],
        ),
        (
            "not sectoral or thematic, small cap",
            [{"field": "category", "op": "in", "value": ["Equity Scheme - Small Cap Fund"]}],
        ),
        # A number reads with its own phrase; a crore amount is a fund size (3, 4).
        (
            "low cost index funds above 5000 crore",
            [
                {"field": "ter_cat_pct", "op": ">=", "value": 50},
                {"field": "category", "op": "in", "value": ["Other Scheme - Index Funds"]},
                {"field": "aum_cr", "op": ">", "value": 5000.0},
            ],
        ),
        (
            "low expense ratio funds with above 15% returns",
            [
                {"field": "ter_cat_pct", "op": ">=", "value": 50},
                {"field": "cagr_3y", "op": ">", "value": 0.15},
            ],
        ),
        (
            "low risk funds above 1000 crore aum",
            [
                {"field": "riskometer_level", "op": "<=", "value": 3},
                {"field": "aum_cr", "op": ">", "value": 1000.0},
            ],
        ),
        ("aum above 1,000 crore", [{"field": "aum_cr", "op": ">", "value": 1000.0}]),
        # Two sizes are two categories; "large and mid cap" is SEBI's one (5).
        (
            "small and mid cap funds",
            [
                {
                    "field": "category",
                    "op": "in",
                    "value": ["Equity Scheme - Small Cap Fund", "Equity Scheme - Mid Cap Fund"],
                }
            ],
        ),
        (
            "large and mid cap funds",
            [{"field": "category", "op": "in", "value": ["Equity Scheme - Large & Mid Cap Fund"]}],
        ),
        (
            "conservative hybrid funds",
            [
                {
                    "field": "category",
                    "op": "in",
                    "value": ["Hybrid Scheme - Conservative Hybrid Fund"],
                }
            ],
        ),
    ],
)
def test_review_findings_read_as_the_investor_meant(
    text: str, added: list[dict[str, object]]
) -> None:
    result = interpret(text)
    assert result.filter["all"][len(result.assumptions) :] == added
    assert result.not_understood == []


def test_unused_numbers_are_reported() -> None:
    assert interpret("beat the benchmark by 2%").not_understood == ["2%"]
    assert interpret("returns above 15% in 2 years").not_understood == ["2 years"]


def test_refinements_narrow_and_remove_what_the_screen_has() -> None:
    base = interpret("diversified equity funds with consistent five-year performance").filter["all"]
    dropped = interpret("drop the sectoral funds", base)
    listed = next(c for c in dropped.filter["all"] if c["field"] == "category")
    assert listed["op"] == "in" and SECTORAL not in listed["value"] and len(listed["value"]) == 11
    # The 5Y half of a consistency request stays with it.
    kept = interpret("remove the return condition", base).filter["all"]
    assert {"field": "cagr_5y_cat_pct", "op": ">=", "value": 50} in kept
    risky = interpret("volatility below 15%").filter["all"]
    assert all(c["field"] != "vol_3y" for c in interpret("remove risk", risky).filter["all"])
    # A kept formula condition is not re-validated here; the screen already ran it.
    formula = [{"field": "edge", "op": ">", "value": 0}]
    assert interpret("TER below 1%", formula).filter["all"][0] == formula[0]
