"""Fundamental Screening engine — disabled by default (ADD §6).

Placeholder — returns a default result. The engine is registered but disabled in
strategy configuration so it can be enabled later without architectural change.
"""

from __future__ import annotations

from decimal import Decimal

from momentum25.domain.engines.base import EvaluationContext
from momentum25.domain.entities.strategy import EngineConfig
from momentum25.domain.value_objects.results import EngineResult, RuleResult


class FundamentalEngine:
    """Evaluates optional fundamental rules (earnings, revenue, ROE, ownership...)."""

    engine_id = "fundamental"

    def evaluate(self, ctx: EvaluationContext, cfg: EngineConfig) -> EngineResult:
        """Evaluate fundamental rules (placeholder — disabled by config)."""
        placeholder_rules = (
            RuleResult(
                rule_id="fundamental_not_yet_implemented",
                engine_id=self.engine_id,
                passed=False,
                raw_value=Decimal("0"),
                threshold=Decimal("0"),
                operator="bool",
                weight=Decimal("1"),
                contribution=Decimal("0"),
                explanation="Fundamental engine placeholder — requires FundamentalDataProvider.",
            ),
        )
        return EngineResult(
            engine_id=self.engine_id,
            rule_results=placeholder_rules,
            engine_score=Decimal("0"),
            passed_gate=False,
        )