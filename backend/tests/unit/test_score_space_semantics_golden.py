"""Golden tests for score-space semantics touched by the 2026-08-09 audit.

Two separate claims are locked here.

**S4 — ``mq_trend_persistence`` (defect, fixed).** The rule counted a
different population in its numerator than in its denominator, producing
ratios above 1 (observed live: "64/63 days (101.5873%)"). Because a failing
rule's ``contribution`` is ``weight * ratio``, a ratio above 1 let a *failing*
rule contribute more than its own weight -- i.e. more than a *passing* one.
Post-fix the ratio is confined to [0, 1] and `contribution <= weight` always.

**S5 — partial credit on failed rules (intentional, not a defect).**
``IMPLEMENTATION_SPEC.md`` §10 specifies:

    normalized_value(rule) in [0,1]  # boolean -> 0/1; numeric -> clamp(...)
    rule.contribution      = rule.weight * normalized_value

so a *numeric* rule's contribution is a continuous function of its measured
value and is deliberately independent of its own pass/fail boolean. A failed
``risk_extension`` at 5% over a 25% ceiling is genuinely better than one at
40%, and the score is meant to say so. Only *gates* are binary in effect:
failing one removes the security from ranking entirely
(``ADD.md`` §19, ``StrategyConfig.gate_rule_ids``). This is therefore not
score leakage, and the observed "failed risk_rr -> 0.38 contribution" is
correct behaviour. The test below pins that semantic so a future reader does
not "fix" it.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from momentum25.domain.engines.momentum_quality import MomentumQualityEngine
from momentum25.domain.entities.strategy import EngineConfig, RuleConfig
from tests.unit.test_engines import _make_context

_MQ_CFG = EngineConfig(
    id="momentum_quality",
    enabled=True,
    weight=Decimal("1"),
    rules=(RuleConfig(id="mq_trend_persistence", weight=Decimal("1")),),
)


def _persistence(closes: list[Decimal]) -> object:
    result = MomentumQualityEngine().evaluate(_make_context(closes=closes), _MQ_CFG)
    return next(r for r in result.rule_results if r.rule_id == "mq_trend_persistence")


# Exactly the boundary that produced 64/63: the rule slices
# `lookback + ma_period` bars, which leaves `lookback + 1` bars with a full
# SMA window against a denominator capped at `lookback`.
_EXACT = 63 + 50
_SURPLUS = _EXACT + 40


@pytest.mark.parametrize("n", [_EXACT, _SURPLUS, _EXACT + 1, 400])
def test_trend_persistence_ratio_never_exceeds_one(n: int) -> None:
    """A monotonically rising series is above its SMA on every countable day."""
    rule = _persistence([Decimal("100") + Decimal("0.5") * i for i in range(n)])
    assert rule.raw_value is not None
    assert Decimal("0") <= rule.raw_value <= Decimal("100"), rule.explanation
    assert "/" in rule.explanation
    num, den = rule.explanation.split(" on ")[1].split(" days")[0].split("/")
    assert int(num) <= int(den), f"numerator exceeds denominator: {rule.explanation}"


def test_trend_persistence_perfect_uptrend_is_exactly_100_percent() -> None:
    rule = _persistence([Decimal("100") + Decimal("0.5") * i for i in range(_EXACT)])
    assert rule.raw_value == Decimal("100")
    assert rule.passed is True
    assert rule.contribution == rule.weight


def test_trend_persistence_contribution_never_exceeds_weight() -> None:
    """The pre-fix ratio > 1 let a failing rule out-contribute a passing one."""
    for closes in (
        [Decimal("100") + Decimal("0.5") * i for i in range(_SURPLUS)],
        [Decimal("100") - Decimal("0.2") * i for i in range(_SURPLUS)],
        [Decimal("100") for _ in range(_SURPLUS)],
    ):
        rule = _persistence(closes)
        assert Decimal("0") <= rule.contribution <= rule.weight, rule.explanation


def test_trend_persistence_is_deterministic() -> None:
    closes = [Decimal("100") + Decimal("0.3") * (i % 17) for i in range(_SURPLUS)]
    first = _persistence(closes)
    for _ in range(3):
        again = _persistence(closes)
        assert (again.raw_value, again.contribution, again.passed, again.explanation) == (
            first.raw_value,
            first.contribution,
            first.passed,
            first.explanation,
        )


def test_failed_numeric_rule_keeps_proportional_partial_credit() -> None:
    """S5: specified behaviour (SPEC §10), not leakage. Do not "fix" this.

    ``mq_trend_persistence`` passes at a 60% ratio. Below that it still
    contributes ``weight * ratio``: a stock above its SMA50 on 55% of days is
    genuinely stronger than one at 10%, and the momentum *score* is meant to
    reflect that even though both fail the rule. Qualification is unaffected --
    this rule is not a gate (see ``test_gate_composition_golden``).
    """
    # A series that oscillates around its SMA50 spends a strictly larger share
    # of days above it the stronger its drift is.
    def ratio_for(drift: str) -> tuple[bool, Decimal]:
        step = Decimal(drift)
        closes = [
            Decimal("100") + step * i + (Decimal("4") if i % 2 else Decimal("0"))
            for i in range(_SURPLUS)
        ]
        rule = _persistence(closes)
        return rule.passed, rule.contribution

    strong_passed, strong = ratio_for("0.5")
    weak_passed, weak = ratio_for("0")
    dead_passed, dead = ratio_for("-0.5")

    assert (strong_passed, weak_passed, dead_passed) == (True, False, False)
    # The mid evaluation fails yet is not zeroed out: it carries proportional
    # credit, strictly between an outright failure and a pass.
    assert Decimal("0") == dead < weak < strong <= Decimal("1")
