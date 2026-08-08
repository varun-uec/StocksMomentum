"""Relative Strength engine (RS rating/percentile, sector/industry/benchmark relative).

Evaluates relative-strength rules against the universe and benchmark using real
RS metrics computed by the RelativeStrengthPipeline. Each rule is deterministic
and fully explainable.

Rules:
  rs_rating:           RS rating percentile (1-99) vs universe — normalized score
  rs_line_uptrend:     RS line slope > 0 over 50-session window
  rs_sector_relative:  Sector-relative RS — compares security RS to sector median
  rs_industry_relative: Industry-relative RS — compares security RS to industry median

Rule inclusion, weight, and thresholds come from ``cfg.rules`` (ADR-005
strategy-as-config): a rule runs only if ``cfg.rules`` is empty (the
"evaluate everything" default) or its id appears in ``cfg.rules``, matched by
id rather than position so removing or reordering rules in a strategy config
behaves correctly.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from momentum25.domain.engines.base import EvaluationContext
from momentum25.domain.entities.strategy import EngineConfig, RuleConfig
from momentum25.domain.value_objects.results import EngineResult, RuleResult


class RelativeStrengthEngine:
    """Evaluates relative-strength rules against the universe and benchmark."""

    engine_id = "relative_strength"

    def evaluate(self, ctx: EvaluationContext, cfg: EngineConfig) -> EngineResult:
        """Evaluate the configured relative-strength rules deterministically.

        Uses the pre-computed RS rating (1-99 percentile) from the IndicatorSet,
        which was populated by the RelativeStrengthPipeline.
        """
        ind = ctx.indicators
        security = ctx.security

        rs_rating = ind.rs_rating
        rs_line_slope = ind.rs_line_slope
        sector_rs_pct = ind.sector_rs_percentile
        industry_rs_pct = ind.industry_rs_percentile

        rule_cfg = {r.id: r for r in cfg.rules}

        def included(rule_id: str) -> bool:
            return not cfg.rules or rule_id in rule_cfg

        evaluators: dict[str, Any] = {
            "rs_rating": lambda rc: self._eval_rs_rating(rs_rating, rc),
            "rs_line_uptrend": lambda rc: self._eval_rs_line_uptrend(rs_line_slope, rc),
            "rs_sector_relative": lambda rc: self._eval_rs_sector_relative(
                rs_rating, sector_rs_pct, security.sector, rc
            ),
            "rs_industry_relative": lambda rc: self._eval_rs_industry_relative(
                rs_rating, industry_rs_pct, security.sector, rc
            ),
        }

        rule_results: list[RuleResult] = [
            evaluators[rule_id](rule_cfg.get(rule_id))
            for rule_id in evaluators
            if included(rule_id)
        ]

        total_weight = sum((r.weight for r in rule_results), Decimal("0"))
        total_contrib = sum((r.contribution for r in rule_results), Decimal("0"))
        engine_score = (total_contrib / total_weight) if total_weight > 0 else Decimal("0")

        return EngineResult(
            engine_id=self.engine_id,
            rule_results=tuple(rule_results),
            engine_score=engine_score,
            passed_gate=False,
            metrics={
                "rs_rating": rs_rating,
                "rs_line_slope": str(rs_line_slope) if rs_line_slope is not None else "N/A",
                "sector_rs_percentile": str(sector_rs_pct) if sector_rs_pct is not None else "N/A",
                "rs_trend": ind.rs_rating_trend or "unknown",
            },
        )

    def _s(self, val: Decimal | None) -> str:
        return f"{val:.4f}" if val is not None else "N/A"

    @staticmethod
    def _weight(rc: RuleConfig | None, default: Decimal) -> Decimal:
        return rc.weight if rc is not None else default

    @staticmethod
    def _param(rc: RuleConfig | None, key: str, default: Decimal) -> Decimal:
        if rc is None or key not in rc.params:
            return default
        return Decimal(str(rc.params[key]))

    def _eval_rs_rating(self, rs_rating: int | None, rc: RuleConfig | None) -> RuleResult:
        rule_id = "rs_rating"
        weight = self._weight(rc, Decimal("2.0"))
        norm_min = self._param(rc, "norm_min", Decimal("70"))
        norm_max = self._param(rc, "norm_max", Decimal("99"))

        if rs_rating is None:
            return RuleResult(
                rule_id=rule_id, engine_id=self.engine_id, passed=False,
                raw_value=None, threshold=norm_min, operator=">=",
                weight=weight, contribution=Decimal("0"),
                explanation="RS rating unavailable — insufficient universe data.",
            )
        raw = Decimal(rs_rating)
        if norm_max <= norm_min:
            normalized = Decimal("0")
        else:
            normalized = (raw - norm_min) / (norm_max - norm_min)
            normalized = max(Decimal("0"), min(Decimal("1"), normalized))

        passed = raw >= norm_min
        contribution = weight * normalized
        return RuleResult(
            rule_id=rule_id, engine_id=self.engine_id, passed=passed,
            raw_value=raw, threshold=norm_min, operator=">=",
            weight=weight, contribution=contribution,
            explanation=(
                f"RS rating {rs_rating} (1-99) {'>=' if passed else '<'} min {norm_min}: "
                f"normalized contribution {self._s(contribution)}."
            ),
        )

    def _eval_rs_line_uptrend(
        self, rs_line_slope: Decimal | None, rc: RuleConfig | None
    ) -> RuleResult:
        rule_id = "rs_line_uptrend"
        weight = self._weight(rc, Decimal("1.0"))
        min_slope = self._param(rc, "min_slope", Decimal("0"))

        if rs_line_slope is None:
            return RuleResult(
                rule_id=rule_id, engine_id=self.engine_id, passed=False,
                raw_value=None, threshold=min_slope, operator=">",
                weight=weight, contribution=Decimal("0"),
                explanation="RS line slope unavailable — insufficient benchmark data.",
            )
        passed = rs_line_slope > min_slope
        return RuleResult(
            rule_id=rule_id, engine_id=self.engine_id, passed=passed,
            raw_value=rs_line_slope, threshold=min_slope, operator=">",
            weight=weight, contribution=weight if passed else Decimal("0"),
            explanation=(
                f"RS line slope {self._s(rs_line_slope)} {'>' if passed else '<='} "
                f"min {self._s(min_slope)}: {'uptrend confirmed' if passed else 'no uptrend'}."
            ),
        )

    def _eval_rs_sector_relative(
        self, rs_rating: int | None, sector_rs_percentile: Decimal | None,
        sector: str | None, rc: RuleConfig | None,
    ) -> RuleResult:
        rule_id = "rs_sector_relative"
        weight = self._weight(rc, Decimal("1.0"))
        threshold = self._param(rc, "threshold", Decimal("50"))

        if rs_rating is None:
            return RuleResult(
                rule_id=rule_id, engine_id=self.engine_id, passed=False,
                raw_value=None, threshold=threshold, operator=">=",
                weight=weight, contribution=Decimal("0"),
                explanation="Sector RS unavailable — rs_rating is None.",
            )

        if sector_rs_percentile is not None:
            passed = sector_rs_percentile >= threshold
            return RuleResult(
                rule_id=rule_id, engine_id=self.engine_id, passed=passed,
                raw_value=sector_rs_percentile, threshold=threshold, operator=">=",
                weight=weight, contribution=weight if passed else Decimal("0"),
                explanation=(
                    f"Sector RS percentile {sector_rs_percentile:.0f} "
                    f"{'≥' if passed else '<'} threshold {threshold:.0f}: "
                    f"{'above sector median' if passed else 'below sector median'}."
                ),
            )

        return RuleResult(
            rule_id=rule_id, engine_id=self.engine_id, passed=False,
            raw_value=Decimal(str(rs_rating)) if rs_rating is not None else None,
            threshold=threshold, operator=">=",
            weight=weight, contribution=Decimal("0"),
            explanation=f"Sector '{sector or 'N/A'}' has no peer data for comparison.",
        )

    def _eval_rs_industry_relative(
        self, rs_rating: int | None, industry_rs_percentile: Decimal | None,
        sector: str | None, rc: RuleConfig | None,
    ) -> RuleResult:
        rule_id = "rs_industry_relative"
        weight = self._weight(rc, Decimal("0.5"))
        threshold = self._param(rc, "threshold", Decimal("50"))

        if rs_rating is None:
            return RuleResult(
                rule_id=rule_id, engine_id=self.engine_id, passed=False,
                raw_value=None, threshold=threshold, operator=">=",
                weight=weight, contribution=Decimal("0"),
                explanation="Industry RS unavailable — rs_rating is None.",
            )

        if industry_rs_percentile is not None:
            passed = industry_rs_percentile >= threshold
            return RuleResult(
                rule_id=rule_id, engine_id=self.engine_id, passed=passed,
                raw_value=industry_rs_percentile, threshold=threshold, operator=">=",
                weight=weight, contribution=weight if passed else Decimal("0"),
                explanation=(
                    f"Industry RS percentile {industry_rs_percentile:.0f} "
                    f"{'≥' if passed else '<'} threshold {threshold:.0f}: "
                    f"{'above industry median' if passed else 'below industry median'}."
                ),
            )

        return RuleResult(
            rule_id=rule_id, engine_id=self.engine_id, passed=False,
            raw_value=Decimal(str(rs_rating)), threshold=threshold, operator=">=",
            weight=weight, contribution=Decimal("0"),
            explanation=(
                f"Industry RS rating {rs_rating} vs median {threshold:.0f}: "
                f"no industry peer data."
            ),
        )
