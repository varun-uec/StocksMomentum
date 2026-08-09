"""The rationale is prose for a human, so it must not leak internal identifiers.

Guards the copy contract of :meth:`ExplainabilityBuilderImpl.build_rationale`:
plain-English condition names, one-decimal scores, no raw rule ids.
"""

from __future__ import annotations

import re
from decimal import Decimal

from momentum25.domain.scoring.explainability import ExplainabilityBuilderImpl
from momentum25.domain.value_objects.results import RuleResult, StockScore


def _rule(rule_id: str, *, passed: bool, engine_id: str = "trend_template") -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        engine_id=engine_id,
        passed=passed,
        raw_value=Decimal("1"),
        threshold=Decimal("0"),
        operator=">",
        weight=Decimal("1"),
        contribution=Decimal("1") if passed else Decimal("0"),
        explanation="",
    )


def _score(**kwargs: object) -> StockScore:
    defaults: dict[str, object] = {
        "security_id": 1,
        "momentum_score": Decimal("39.94201234"),
        "buy_setup_score": Decimal("60.98470987"),
        "hard_filters_passed": False,
        "engine_results": (),
    }
    defaults.update(kwargs)
    return StockScore(**defaults)  # type: ignore[arg-type]


def test_rationale_has_no_rule_ids_or_raw_decimals() -> None:
    failing = [
        "tt_close_above_sma150_200",
        "tt_sma150_above_sma200",
        "tt_sma200_uptrend",
        "tt_sma_stack",
        "tt_rs_rating_min",
    ]
    rules = [_rule(r, passed=False) for r in failing] + [
        _rule("tt_close_above_sma50", passed=True)
    ]

    text = ExplainabilityBuilderImpl().build_rationale(_score(), rules)

    for rule_id in failing:
        assert rule_id not in text, f"raw rule id {rule_id} leaked into rationale: {text}"
    assert not re.search(r"\d+\.\d{2,}", text), f"unrounded score in rationale: {text}"
    assert "39.9" in text and "61.0" in text
    assert "1 of 6 conditions met." in text
    # Gate failures lead and are named once, not repeated as generic failures.
    assert text.count("close above the 150- and 200-day averages") == 1
    # Only the first few failures are named; the rest are summarised.
    assert "blocked by the hard gate" in text and "plus 2 others" in text


def test_rationale_when_all_gates_clear() -> None:
    rules = [_rule("tt_close_above_sma50", passed=True)]
    text = ExplainabilityBuilderImpl().build_rationale(
        _score(hard_filters_passed=True), rules
    )
    assert "clears every hard gate" in text
    assert "Not met" not in text
