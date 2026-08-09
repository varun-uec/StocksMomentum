"""Trend Template engine (Minervini 8-point trend gate).

Evaluates the Minervini trend-template criteria as a hard gate. Each rule is
deterministic and independently explainable. Missing indicators produce explicit
None-rule results rather than crashing the orchestrator (NFR determinism contract).

Rule IDs match the strategy JSON config (IMPLEMENTATION_SPEC.md §9):
  tt_close_above_sma150_200, tt_sma150_above_sma200, tt_sma200_uptrend,
  tt_sma_stack, tt_close_above_sma50, tt_above_52w_low, tt_near_52w_high,
  tt_rs_rating_min

Rule inclusion and per-rule weight/threshold come from ``cfg.rules`` (ADR-005
strategy-as-config): a rule is evaluated only if ``cfg.rules`` is empty (the
"evaluate everything" default, used by callers with no strategy context) or
its id appears in ``cfg.rules``. Params/weight are read from the matching
``RuleConfig``, falling back to the documented defaults when absent.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from momentum25.domain.engines.base import EvaluationContext
from momentum25.domain.entities.strategy import EngineConfig, RuleConfig
from momentum25.domain.value_objects.results import EngineResult, RuleResult


class TrendTemplateEngine:
    """Evaluates the Minervini 8-point trend-template criteria as a hard gate."""

    engine_id = "trend_template"

    def evaluate(self, ctx: EvaluationContext, cfg: EngineConfig) -> EngineResult:
        """Evaluate the configured trend-template rules and return the aggregated result.

        Rules (per IMPLEMENTATION_SPEC.md §9), each included only if declared
        in ``cfg.rules`` (or all of them, if ``cfg.rules`` is empty):
        1. tt_close_above_sma150_200: close > sma150 AND close > sma200
        2. tt_sma150_above_sma200: sma150 > sma200
        3. tt_sma200_uptrend: sma200_slope_pct > params.min_slope_pct (default 0)
        4. tt_sma_stack: sma50 > sma150 AND sma50 > sma200. Equivalent to the
           full chain sma50 > sma150 > sma200 only jointly with rule 2
           (tt_sma150_above_sma200) — enforced below when both are configured.
        5. tt_close_above_sma50: close > sma50
        6. tt_above_52w_low: pct_above_low_52w >= params.min_pct (default 30)
        7. tt_near_52w_high: pct_below_high_52w <= params.max_pct (default 25)
        8. tt_rs_rating_min: rs_rating >= params.min (default 70)
        """
        ind = ctx.indicators
        close = ctx.series.latest.close if ctx.series.latest else None
        rule_cfg = {r.id: r for r in cfg.rules}

        def included(rule_id: str) -> bool:
            return not cfg.rules or rule_id in rule_cfg

        if included("tt_sma_stack") and not included("tt_sma150_above_sma200"):
            raise ValueError(
                "tt_sma_stack requires tt_sma150_above_sma200 to also be configured: "
                "its 'full SMA stack' equivalence (sma50 > sma150 > sma200) holds only "
                "as their conjunction, not for tt_sma_stack alone."
            )

        evaluators: dict[str, Any] = {
            "tt_close_above_sma150_200": lambda rc: self._eval_tt_close_above_sma150_200(
                close, ind.sma150, ind.sma200, rc
            ),
            "tt_sma150_above_sma200": lambda rc: self._eval_tt_sma150_above_sma200(
                ind.sma150, ind.sma200, rc
            ),
            "tt_sma200_uptrend": lambda rc: self._eval_tt_sma200_uptrend(
                ind.sma200_slope_pct, rc
            ),
            "tt_sma_stack": lambda rc: self._eval_tt_sma_stack(
                ind.sma50, ind.sma150, ind.sma200, rc
            ),
            "tt_close_above_sma50": lambda rc: self._eval_tt_close_above_sma50(
                close, ind.sma50, rc
            ),
            "tt_above_52w_low": lambda rc: self._eval_tt_above_52w_low(
                close, ind.low_52w, ind.pct_above_low_52w, rc
            ),
            "tt_near_52w_high": lambda rc: self._eval_tt_near_52w_high(
                close, ind.high_52w, ind.pct_below_high_52w, rc
            ),
            "tt_rs_rating_min": lambda rc: self._eval_tt_rs_rating_min(ind.rs_rating, rc),
        }

        checklist: dict[str, bool] = {}
        rule_results: list[RuleResult] = []
        for rule_id, evaluator in evaluators.items():
            if not included(rule_id):
                continue
            result = evaluator(rule_cfg.get(rule_id))
            checklist[rule_id] = result.passed
            rule_results.append(result)

        all_passed = all(checklist.values()) if checklist else False
        passed_count = sum(checklist.values())
        score = (
            Decimal(str(passed_count)) / Decimal(str(len(checklist)))
            if checklist
            else Decimal("0")
        )

        return EngineResult(
            engine_id=self.engine_id,
            rule_results=tuple(rule_results),
            engine_score=score,
            passed_gate=all_passed,
            metrics={"checklist": checklist},
        )

    # ── private rule helpers ─────────────────────────────────────────────

    def _s(self, val: Decimal | None) -> str:
        """Safe string representation for explanations."""
        return f"{val:.4f}" if val is not None else "N/A"

    @staticmethod
    def _weight(rc: RuleConfig | None, default: Decimal) -> Decimal:
        return rc.weight if rc is not None else default

    @staticmethod
    def _param(rc: RuleConfig | None, key: str, default: Decimal) -> Decimal:
        if rc is None or key not in rc.params:
            return default
        return Decimal(str(rc.params[key]))

    def _eval_tt_close_above_sma150_200(
        self,
        close: Decimal | None,
        sma150: Decimal | None,
        sma200: Decimal | None,
        rc: RuleConfig | None,
    ) -> RuleResult:
        rule_id = "tt_close_above_sma150_200"
        weight = self._weight(rc, Decimal("1"))
        if close is None or sma150 is None or sma200 is None:
            return RuleResult(
                rule_id=rule_id,
                engine_id=self.engine_id,
                passed=False,
                raw_value=close,
                threshold=None,
                operator="bool",
                weight=weight,
                contribution=Decimal("0"),
                explanation="Insufficient data: close, sma150, or sma200 is None.",
            )
        passed = close > sma150 and close > sma200
        return RuleResult(
            rule_id=rule_id,
            engine_id=self.engine_id,
            passed=passed,
            raw_value=close,
            threshold=Decimal("0"),
            operator="> sma150 AND > sma200",
            weight=weight,
            contribution=weight if passed else Decimal("0"),
            explanation=(
                f"Close {self._s(close)} {'>' if passed else '<='} "
                f"SMA150 {self._s(sma150)} and SMA200 {self._s(sma200)}."
            ),
        )

    def _eval_tt_sma150_above_sma200(
        self, sma150: Decimal | None, sma200: Decimal | None, rc: RuleConfig | None
    ) -> RuleResult:
        rule_id = "tt_sma150_above_sma200"
        weight = self._weight(rc, Decimal("1"))
        if sma150 is None or sma200 is None:
            return RuleResult(
                rule_id=rule_id,
                engine_id=self.engine_id,
                passed=False,
                raw_value=sma150,
                threshold=sma200,
                operator=">",
                weight=weight,
                contribution=Decimal("0"),
                explanation="Insufficient data: sma150 or sma200 is None.",
            )
        passed = sma150 > sma200
        return RuleResult(
            rule_id=rule_id,
            engine_id=self.engine_id,
            passed=passed,
            raw_value=sma150,
            threshold=sma200,
            operator=">",
            weight=weight,
            contribution=weight if passed else Decimal("0"),
            explanation=(
                f"SMA150 {self._s(sma150)} {'>' if passed else '<='} SMA200 {self._s(sma200)}."
            ),
        )

    def _eval_tt_sma200_uptrend(
        self, slope_pct: Decimal | None, rc: RuleConfig | None
    ) -> RuleResult:
        rule_id = "tt_sma200_uptrend"
        weight = self._weight(rc, Decimal("1"))
        min_slope_pct = self._param(rc, "min_slope_pct", Decimal("0"))
        if slope_pct is None:
            return RuleResult(
                rule_id=rule_id,
                engine_id=self.engine_id,
                passed=False,
                raw_value=slope_pct,
                threshold=min_slope_pct,
                operator=">",
                weight=weight,
                contribution=Decimal("0"),
                explanation="Insufficient data: sma200 slope is None.",
            )
        passed = slope_pct > min_slope_pct
        return RuleResult(
            rule_id=rule_id,
            engine_id=self.engine_id,
            passed=passed,
            raw_value=slope_pct,
            threshold=min_slope_pct,
            operator=">",
            weight=weight,
            contribution=weight if passed else Decimal("0"),
            explanation=(
                f"SMA200 slope {self._s(slope_pct)}% {'>' if passed else '<='} "
                f"{self._s(min_slope_pct)}% (trending up over 22 sessions)."
            ),
        )

    def _eval_tt_sma_stack(
        self,
        sma50: Decimal | None,
        sma150: Decimal | None,
        sma200: Decimal | None,
        rc: RuleConfig | None,
    ) -> RuleResult:
        rule_id = "tt_sma_stack"
        weight = self._weight(rc, Decimal("1"))
        if sma50 is None or sma150 is None or sma200 is None:
            return RuleResult(
                rule_id=rule_id,
                engine_id=self.engine_id,
                passed=False,
                raw_value=sma50,
                threshold=None,
                operator="bool",
                weight=weight,
                contribution=Decimal("0"),
                explanation="Insufficient data: sma50, sma150, or sma200 is None.",
            )
        passed = sma50 > sma150 and sma50 > sma200
        return RuleResult(
            rule_id=rule_id,
            engine_id=self.engine_id,
            passed=passed,
            raw_value=sma50,
            threshold=Decimal("0"),
            operator="> sma150 AND > sma200",
            weight=weight,
            contribution=weight if passed else Decimal("0"),
            explanation=(
                f"SMA50 {self._s(sma50)} {'>' if passed else '<='} "
                f"SMA150 {self._s(sma150)} and SMA200 {self._s(sma200)} (bullish stack)."
            ),
        )

    def _eval_tt_close_above_sma50(
        self, close: Decimal | None, sma50: Decimal | None, rc: RuleConfig | None
    ) -> RuleResult:
        rule_id = "tt_close_above_sma50"
        weight = self._weight(rc, Decimal("1"))
        if close is None or sma50 is None:
            return RuleResult(
                rule_id=rule_id,
                engine_id=self.engine_id,
                passed=False,
                raw_value=close,
                threshold=sma50,
                operator=">",
                weight=weight,
                contribution=Decimal("0"),
                explanation="Insufficient data: close or sma50 is None.",
            )
        passed = close > sma50
        return RuleResult(
            rule_id=rule_id,
            engine_id=self.engine_id,
            passed=passed,
            raw_value=close,
            threshold=sma50,
            operator=">",
            weight=weight,
            contribution=weight if passed else Decimal("0"),
            explanation=f"Close {self._s(close)} {'>' if passed else '<='} SMA50 {self._s(sma50)}.",
        )

    def _eval_tt_above_52w_low(
        self,
        close: Decimal | None,
        low_52w: Decimal | None,
        pct_above_low_52w: Decimal | None,
        rc: RuleConfig | None,
    ) -> RuleResult:
        rule_id = "tt_above_52w_low"
        weight = self._weight(rc, Decimal("1"))
        threshold_pct = self._param(rc, "min_pct", Decimal("30"))
        if close is None or low_52w is None:
            return RuleResult(
                rule_id=rule_id,
                engine_id=self.engine_id,
                passed=False,
                raw_value=close,
                threshold=threshold_pct,
                operator=">=",
                weight=weight,
                contribution=Decimal("0"),
                explanation="Insufficient data: close or low_52w is None.",
            )
        actual_pct = pct_above_low_52w if pct_above_low_52w is not None else (
            (close - low_52w) / low_52w * Decimal("100")
        )
        passed = actual_pct >= threshold_pct
        return RuleResult(
            rule_id=rule_id,
            engine_id=self.engine_id,
            passed=passed,
            raw_value=actual_pct,
            threshold=threshold_pct,
            operator=">=",
            weight=weight,
            contribution=weight if passed else Decimal("0"),
            explanation=(
                f"Pct above 52w low {self._s(actual_pct)}% {'>=' if passed else '<'} "
                f"threshold {self._s(threshold_pct)}%."
            ),
        )

    def _eval_tt_near_52w_high(
        self,
        close: Decimal | None,
        high_52w: Decimal | None,
        pct_below_high_52w: Decimal | None,
        rc: RuleConfig | None,
    ) -> RuleResult:
        rule_id = "tt_near_52w_high"
        weight = self._weight(rc, Decimal("1"))
        threshold_pct = self._param(rc, "max_pct", Decimal("25"))
        if close is None or high_52w is None:
            return RuleResult(
                rule_id=rule_id,
                engine_id=self.engine_id,
                passed=False,
                raw_value=close,
                threshold=threshold_pct,
                operator="<=",
                weight=weight,
                contribution=Decimal("0"),
                explanation="Insufficient data: close or high_52w is None.",
            )
        actual_pct = pct_below_high_52w if pct_below_high_52w is not None else (
            (high_52w - close) / high_52w * Decimal("100")
        )
        passed = actual_pct <= threshold_pct
        return RuleResult(
            rule_id=rule_id,
            engine_id=self.engine_id,
            passed=passed,
            raw_value=actual_pct,
            threshold=threshold_pct,
            operator="<=",
            weight=weight,
            contribution=weight if passed else Decimal("0"),
            explanation=(
                f"Pct below 52w high {self._s(actual_pct)}% {'<=' if passed else '>'} "
                f"threshold {self._s(threshold_pct)}%."
            ),
        )

    def _eval_tt_rs_rating_min(
        self, rs_rating: int | None, rc: RuleConfig | None
    ) -> RuleResult:
        rule_id = "tt_rs_rating_min"
        weight = self._weight(rc, Decimal("1.5"))
        threshold = self._param(rc, "min", Decimal("70"))
        if rs_rating is None:
            return RuleResult(
                rule_id=rule_id,
                engine_id=self.engine_id,
                passed=False,
                raw_value=None,
                threshold=threshold,
                operator=">=",
                weight=weight,
                contribution=Decimal("0"),
                explanation="Insufficient data: rs_rating is None.",
            )
        raw = Decimal(rs_rating)
        passed = raw >= threshold
        return RuleResult(
            rule_id=rule_id,
            engine_id=self.engine_id,
            passed=passed,
            raw_value=raw,
            threshold=threshold,
            operator=">=",
            weight=weight,
            contribution=weight if passed else Decimal("0"),
            explanation=f"RS rating {rs_rating} {'>=' if passed else '<'} {threshold}.",
        )
