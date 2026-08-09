"""Scoring engine implementation — combines engine results into StockScore.

Implements the weighted matrix from ``IMPLEMENTATION_SPEC.md`` §10 using only
``Decimal`` arithmetic. Scores are quantized to 4 decimal places at the boundary.
"""

from __future__ import annotations

from decimal import Decimal

from momentum25.domain.entities.strategy import EngineConfig, StrategyConfig
from momentum25.domain.value_objects.results import EngineResult, StockScore

_SCORE_QUANT = Decimal("0.0001")


class ScoringEngineImpl:
    """Combines engine results into momentum and buy-setup scores.

    Per SPEC §10:

        engine_score        = Σ rule.contribution (sorted by rule_id) / Σ rule.weight
        momentum_score      = 100 * Σ(engine_weight * engine_score) / Σ engine_weight
        buy_setup_score     = 100 * Σ(setup_weight  * engine_score) / Σ setup_weight
        hard_filters_passed = all gate engines passed

    The per-engine ``engine_score`` is already computed by each evaluation engine;
    this class only combines them into the final momentum / buy-setup scores.

    Gate engines (``EngineConfig.gate``, e.g. the Trend Template) are excluded
    from both weighted scores: among qualifiers a gate engine's score is 1.0 by
    construction (``passed_gate`` requires every rule to pass), so it has zero
    cross-sectional variance and contributes nothing but a constant offset.
    Dropping it is provably rank-neutral and removes an artificial score floor.
    """

    def score(
        self, security_id: int, engine_results: list[EngineResult], cfg: StrategyConfig
    ) -> StockScore:
        """Return a :class:`StockScore` for ``security_id``.

        Args:
            security_id: The security being scored.
            engine_results: Results from all enabled engines.
            cfg: The strategy configuration (weights and gate flags).

        Returns:
            A StockScore with momentum/buy-setup scores and hard-filter status.
        """
        engine_cfg_by_id = {e.id: e for e in cfg.enabled_engines()}
        hard_filters_passed = self._compute_hard_filters_passed(
            engine_results, engine_cfg_by_id
        )

        momentum_score = self._weighted_score(
            engine_results, cfg.momentum_weights, engine_cfg_by_id
        )
        buy_setup_score = self._weighted_score(
            engine_results, cfg.buy_setup_weights, engine_cfg_by_id
        )

        return StockScore(
            security_id=security_id,
            momentum_score=momentum_score,
            buy_setup_score=buy_setup_score,
            engine_results=tuple(engine_results),
            hard_filters_passed=hard_filters_passed,
        )

    @staticmethod
    def _compute_hard_filters_passed(
        engine_results: list[EngineResult],
        engine_cfg_by_id: dict[str, EngineConfig],
    ) -> bool:
        """Return whether every configured gate passed.

        A gate applies either at the engine level (``EngineConfig.gate``, e.g.
        the Trend Template) or at the rule level (``RuleConfig.gate``, e.g. the
        minimum-liquidity floor inside Volume & Accumulation, whose parent
        engine otherwise only scores). Checking rule-level gates directly
        against ``RuleResult.passed`` — rather than relying solely on the
        parent engine's own ``passed_gate`` — ensures a rule-level gate is
        enforced even when the engine it lives in is not itself a gate engine.
        If no gate is configured at all, fall back to requiring every
        evaluated engine to have passed its own gate.
        """
        engine_gate_ids = {eid for eid, ec in engine_cfg_by_id.items() if ec.gate}
        rule_gate_ids = {
            (ec.id, rc.id) for ec in engine_cfg_by_id.values() for rc in ec.rules if rc.gate
        }

        if not engine_gate_ids and not rule_gate_ids:
            # Backward-compatible fallback: no explicit gates → all engines must pass.
            return all(er.passed_gate for er in engine_results)

        for er in engine_results:
            if er.engine_id in engine_gate_ids and not er.passed_gate:
                return False
            for rr in er.rule_results:
                if (er.engine_id, rr.rule_id) in rule_gate_ids and not rr.passed:
                    return False
        return True

    @staticmethod
    def _weighted_score(
        engine_results: list[EngineResult],
        weights: dict[str, Decimal],
        engine_cfg_by_id: dict[str, EngineConfig],
    ) -> Decimal:
        """Compute a weighted percentage score from engine results.

        If ``weights`` is empty, fall back to the engine's configured weight so
        that a minimal single-engine strategy still produces a meaningful score.
        Gate engines are excluded (see class docstring).
        """
        ranked_results = [
            er
            for er in engine_results
            if not engine_cfg_by_id[er.engine_id].gate
        ]

        if weights:
            total_weight = sum(
                (weights.get(er.engine_id, Decimal("0")) for er in ranked_results),
                Decimal("0"),
            )
            weighted_sum = sum(
                weights.get(er.engine_id, Decimal("0")) * er.engine_score
                for er in ranked_results
            )
        else:
            total_weight = sum(
                (engine_cfg_by_id[er.engine_id].weight for er in ranked_results),
                Decimal("0"),
            )
            weighted_sum = sum(
                engine_cfg_by_id[er.engine_id].weight * er.engine_score
                for er in ranked_results
            )

        if total_weight == 0:
            return Decimal("0")

        return (Decimal("100") * weighted_sum / total_weight).quantize(_SCORE_QUANT)
