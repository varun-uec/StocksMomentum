"""Pattern Recognition engine — orchestrates pattern detectors.

Runs all registered pattern detectors and converts detections to rule results.
Each pattern becomes a rule with a quality score contribution.
"""

from __future__ import annotations

from decimal import Decimal

from momentum25.domain.engines.base import EvaluationContext
from momentum25.domain.entities.strategy import EngineConfig
from momentum25.domain.patterns.registry import get_pattern_registry
from momentum25.domain.value_objects.results import EngineResult, RuleResult


class PatternEngine:
    """Runs registered pattern detectors and converts detections to rule results."""

    engine_id = "pattern"

    def evaluate(self, ctx: EvaluationContext, cfg: EngineConfig) -> EngineResult:
        """Evaluate all registered pattern detectors.

        Each pattern becomes a rule. If a pattern is detected, the rule passes
        with a contribution proportional to its quality score.
        """
        registry = get_pattern_registry()
        detectors = registry.all_detectors()

        if not detectors:
            return EngineResult(
                engine_id=self.engine_id,
                rule_results=(
                    RuleResult(
                        rule_id="pattern_no_detectors",
                        engine_id=self.engine_id,
                        passed=False,
                        raw_value=Decimal("0"),
                        threshold=Decimal("0"),
                        operator="bool",
                        weight=Decimal("1"),
                        contribution=Decimal("0"),
                        explanation="No pattern detectors registered.",
                    ),
                ),
                engine_score=Decimal("0"),
                passed_gate=False,
            )

        # Convert series to lists of Decimal for pattern detectors
        close = [Decimal(str(b.close)) for b in ctx.series.bars]
        high = [Decimal(str(b.high)) for b in ctx.series.bars]
        low = [Decimal(str(b.low)) for b in ctx.series.bars]
        volume = [b.volume for b in ctx.series.bars]

        rule_results: list[RuleResult] = []
        total_contrib = Decimal("0")
        total_weight = Decimal("0")

        for pattern_name, detector in sorted(detectors.items()):
            result = detector.detect(close, high, low, volume)
            weight = Decimal("1.0")
            total_weight += weight

            if result.detected:
                quality = Decimal(str(result.quality_score)) / Decimal("100")
                contribution = weight * quality
                total_contrib += contribution
                rule_results.append(
                    RuleResult(
                        rule_id=f"pattern_{pattern_name}",
                        engine_id=self.engine_id,
                        passed=True,
                        raw_value=Decimal(str(result.quality_score)),
                        threshold=Decimal("50"),
                        operator=">=",
                        weight=weight,
                        contribution=contribution,
                        explanation=result.explanation,
                    )
                )
            else:
                rule_results.append(
                    RuleResult(
                        rule_id=f"pattern_{pattern_name}",
                        engine_id=self.engine_id,
                        passed=False,
                        raw_value=Decimal("0"),
                        threshold=Decimal("50"),
                        operator=">=",
                        weight=weight,
                        contribution=Decimal("0"),
                        explanation=result.explanation,
                    )
                )

        engine_score = (total_contrib / total_weight) if total_weight > 0 else Decimal("0")

        return EngineResult(
            engine_id=self.engine_id,
            rule_results=tuple(rule_results),
            engine_score=engine_score,
            passed_gate=False,
            metrics={"patterns_detected": sum(1 for r in rule_results if r.passed)},
        )