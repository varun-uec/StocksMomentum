"""Golden test: gate composition has exactly one definition.

Before this test, ``ExplainabilityBuilderImpl`` decided what "blocks
qualification" from a hardcoded engine-name heuristic
(``engine_id in {"trend_template", "risk"}``) while ``ScoringEngineImpl``
read ``EngineConfig.gate``/``RuleConfig.gate``. The two disagreed in both
directions on the production strategy: the explainer invented a gate
(``risk_rr``) and missed a real one (``vol_liquidity_min``), so a stock could
be returned with ``overall_passed=True`` *and* a non-empty
``hard_filter_failures``.

Both now derive from :meth:`StrategyConfig.gate_rule_ids`, and the contract
asserted here is the biconditional the user-facing page depends on:

    hard_filter_failures == ()  <=>  overall_passed

Score space is untouched by this change: ``momentum_score`` /
``buy_setup_score`` are produced by ``ScoringEngineImpl._weighted_score``,
which never consulted the explainer. Only the *reported reason* moves.
"""

from __future__ import annotations

from decimal import Decimal
from itertools import product
from pathlib import Path

from momentum25.domain.entities.strategy import StrategyConfig
from momentum25.domain.scoring.explainability import ExplainabilityBuilderImpl
from momentum25.domain.scoring.scoring_engine import ScoringEngineImpl
from momentum25.domain.value_objects.results import EngineResult, RuleResult
from momentum25.infrastructure.config.strategy_loader import load_strategy_file

_STRATEGY_PATH = (
    Path(__file__).resolve().parents[3]
    / "docs"
    / "architecture"
    / "strategies"
    / "minervini_trend_template.json"
)

# The production strategy's gate set, read off the config by hand. Golden:
# changing it means changing what qualifies, which is a methodology decision.
_EXPECTED_GATES = frozenset(
    {
        "tt_close_above_sma150_200",
        "tt_sma150_above_sma200",
        "tt_sma200_uptrend",
        "tt_sma_stack",
        "tt_close_above_sma50",
        "tt_above_52w_low",
        "tt_near_52w_high",
        "tt_rs_rating_min",
        "vol_liquidity_min",
    }
)


def _config() -> StrategyConfig:
    return load_strategy_file(_STRATEGY_PATH).config


def _rule(rule_id: str, engine_id: str, *, passed: bool) -> RuleResult:
    return RuleResult(
        rule_id=rule_id,
        engine_id=engine_id,
        passed=passed,
        operator=">",
        weight=Decimal("1"),
        contribution=Decimal("1") if passed else Decimal("0"),
        explanation="",
    )


def test_production_gate_set_is_golden() -> None:
    assert _config().gate_rule_ids() == _EXPECTED_GATES


def test_risk_engine_is_not_a_gate() -> None:
    """The pre-fix heuristic treated every risk rule as blocking. It is not."""
    gates = _config().gate_rule_ids()
    assert "risk_rr" not in gates
    assert "risk_extension" not in gates
    assert "risk_atr" not in gates


def test_no_gate_configured_falls_back_to_every_rule() -> None:
    """Mirrors ScoringEngineImpl's own "no gates -> all engines must pass" fallback."""
    cfg = _config()
    ungated = StrategyConfig(
        name=cfg.name,
        version=cfg.version,
        engines=tuple(
            type(e)(
                id=e.id,
                enabled=e.enabled,
                weight=e.weight,
                rules=tuple(type(r)(id=r.id, weight=r.weight, params=r.params) for r in e.rules),
                gate=False,
            )
            for e in cfg.engines
        ),
    )
    all_rule_ids = {r.id for e in ungated.enabled_engines() for r in e.rules}
    assert ungated.gate_rule_ids() == all_rule_ids


def test_hard_filter_failures_iff_not_overall_passed() -> None:
    """The invariant the stock detail page renders, over every gate outcome."""
    cfg = _config()
    builder = ExplainabilityBuilderImpl().for_strategy(cfg)
    scoring = ScoringEngineImpl()
    gates = cfg.gate_rule_ids()

    # Exhaustive over (trend-template all-pass?, liquidity gate pass?,
    # every non-gate rule pass?) -- the three independent axes that can move
    # `hard_filters_passed`.
    for tt_pass, liq_pass, other_pass in product((True, False), repeat=3):
        engine_results = []
        for engine in cfg.enabled_engines():
            rules = tuple(
                _rule(
                    r.id,
                    engine.id,
                    passed=(
                        tt_pass
                        if engine.gate
                        else liq_pass
                        if r.gate
                        else other_pass
                    ),
                )
                for r in engine.rules
            )
            engine_results.append(
                EngineResult(
                    engine_id=engine.id,
                    rule_results=rules,
                    engine_score=Decimal("0.5"),
                    passed_gate=all(r.passed for r in rules) if rules else False,
                )
            )

        score = scoring.score(1, engine_results, cfg)
        flat = [rr for er in engine_results for rr in er.rule_results]
        explanation = builder.build_explanation(score, flat)

        assert explanation.overall_passed == score.hard_filters_passed
        assert (explanation.hard_filter_failures == ()) == explanation.overall_passed, (
            f"gate/explanation disagreement at "
            f"tt={tt_pass} liq={liq_pass} other={other_pass}: "
            f"passed={explanation.overall_passed} "
            f"failures={explanation.hard_filter_failures}"
        )
        assert set(explanation.hard_filter_failures) <= gates


def test_rationale_names_only_configured_gates() -> None:
    """'blocked by the hard gate on ...' must never cite a non-gate rule."""
    cfg = _config()
    builder = ExplainabilityBuilderImpl().for_strategy(cfg)
    scoring = ScoringEngineImpl()

    # Everything passes except risk_rr -- the exact SANSERA shape from the audit.
    engine_results = []
    for engine in cfg.enabled_engines():
        rules = tuple(
            _rule(r.id, engine.id, passed=r.id != "risk_rr") for r in engine.rules
        )
        engine_results.append(
            EngineResult(
                engine_id=engine.id,
                rule_results=rules,
                engine_score=Decimal("0.9"),
                passed_gate=all(r.passed for r in rules) if rules else False,
            )
        )

    score = scoring.score(1, engine_results, cfg)
    flat = [rr for er in engine_results for rr in er.rule_results]
    explanation = builder.build_explanation(score, flat)

    assert explanation.overall_passed is True
    assert explanation.hard_filter_failures == ()
    assert "blocked by the hard gate" not in explanation.overall_rationale
    assert "It clears every hard gate." in explanation.overall_rationale
