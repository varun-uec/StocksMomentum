"""Breakout Evaluation engine (pivot/breakout quality, follow-through, false breakout).

Evaluates breakout quality and confirmation rules deterministically:
  bo_pivot_breakout:   Pivot/breakout quality — price vs recent range
  bo_followthrough:    Follow-through confirmation over subsequent sessions
  bo_false_breakout:   False breakout detection (closes back below breakout level)

Rule inclusion and weight come from ``cfg.rules`` (ADR-005 strategy-as-config):
a rule runs only if ``cfg.rules`` is empty (the "evaluate everything" default)
or its id appears in ``cfg.rules``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from momentum25.domain.engines.base import EvaluationContext
from momentum25.domain.entities.market_data import OHLCVSeries
from momentum25.domain.entities.strategy import EngineConfig, RuleConfig
from momentum25.domain.value_objects.results import EngineResult, RuleResult


class BreakoutEngine:
    """Evaluates breakout quality and confirmation rules."""

    engine_id = "breakout"

    def evaluate(self, ctx: EvaluationContext, cfg: EngineConfig) -> EngineResult:
        """Evaluate the configured breakout rules deterministically.

        Uses OHLCV series to detect:
        1. bo_pivot_breakout: Current close vs recent 20-day high range.
        2. bo_followthrough: Price holding above breakout level (SMA5 vs SMA10).
        3. bo_false_breakout: No close-back below the recent range midpoint.
        """
        series = ctx.series
        rule_cfg = {r.id: r for r in cfg.rules}

        def included(rule_id: str) -> bool:
            return not cfg.rules or rule_id in rule_cfg

        evaluators: dict[str, Any] = {
            "bo_pivot_breakout": lambda rc: self._eval_bo_pivot_breakout(series, rc),
            "bo_followthrough": lambda rc: self._eval_bo_followthrough(series, rc),
            "bo_false_breakout": lambda rc: self._eval_bo_false_breakout(series, rc),
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
            passed_gate=False,  # Breakout is not a gate engine
        )

    # ── Rule helpers ─────────────────────────────────────────────────────────

    def _s(self, val: Decimal | None) -> str:
        return f"{val:.4f}" if val is not None else "N/A"

    @staticmethod
    def _weight(rc: RuleConfig | None, default: Decimal) -> Decimal:
        return rc.weight if rc is not None else default

    def _compute_recent_range(self, series: OHLCVSeries) -> tuple[Decimal | None, Decimal | None]:
        """Compute the high and low over the last 20 bars."""
        bars = series.bars
        if not bars or len(bars) < 20:
            return None, None
        recent = bars[-20:]
        high_20 = max(b.high for b in recent)
        low_20 = min(b.low for b in recent)
        return high_20, low_20

    def _eval_bo_pivot_breakout(self, series: OHLCVSeries, rc: RuleConfig | None) -> RuleResult:
        rule_id = "bo_pivot_breakout"
        weight = self._weight(rc, Decimal("1.5"))
        bars = series.bars
        latest_bar = series.latest
        if latest_bar is None or not bars or len(bars) < 20:
            return RuleResult(
                rule_id=rule_id,
                engine_id=self.engine_id,
                passed=False,
                raw_value=None,
                threshold=Decimal("0"),
                operator="bool",
                weight=weight,
                contribution=Decimal("0"),
                explanation="Insufficient data for pivot breakout detection.",
            )
        high_20, low_20 = self._compute_recent_range(series)
        if high_20 is None or low_20 is None or high_20 == low_20:
            return RuleResult(
                rule_id=rule_id,
                engine_id=self.engine_id,
                passed=False,
                raw_value=None,
                threshold=Decimal("0"),
                operator="bool",
                weight=weight,
                contribution=Decimal("0"),
                explanation="Cannot compute 20-day range.",
            )

        range_size = high_20 - low_20
        # Breakout quality: how close is close to 20-day high?
        pct_of_range = (latest_bar.close - low_20) / range_size * Decimal("100")
        # Pass if close is in the top 30% of the range
        passed = pct_of_range >= Decimal("70")
        # Normalized contribution: (pct - 50) / 50 clamped to [0, 1]
        normalized = max(Decimal("0"), min(Decimal("1"),
            (pct_of_range - Decimal("50")) / Decimal("50")))
        contribution = weight * normalized
        return RuleResult(
            rule_id=rule_id,
            engine_id=self.engine_id,
            passed=passed,
            raw_value=pct_of_range,
            threshold=Decimal("70"),
            operator=">=",
            weight=weight,
            contribution=contribution,
            explanation=(
                f"Close at {self._s(pct_of_range)}% of 20d range "
                f"({'Breakout zone' if passed else 'Below breakout'})."
            ),
        )

    def _eval_bo_followthrough(self, series: OHLCVSeries, rc: RuleConfig | None) -> RuleResult:
        rule_id = "bo_followthrough"
        weight = self._weight(rc, Decimal("1.0"))
        bars = series.bars
        if not bars or len(bars) < 10:
            return RuleResult(
                rule_id=rule_id,
                engine_id=self.engine_id,
                passed=False,
                raw_value=None,
                threshold=Decimal("0"),
                operator=">",
                weight=weight,
                contribution=Decimal("0"),
                explanation="Insufficient data for follow-through detection.",
            )
        # Simple follow-through: latest close > SMA(5) > SMA(10)
        closes = [float(b.close) for b in bars]
        if len(closes) < 10:
            return RuleResult(
                rule_id=rule_id,
                engine_id=self.engine_id,
                passed=False,
                raw_value=None,
                threshold=Decimal("0"),
                operator=">",
                weight=weight,
                contribution=Decimal("0"),
                explanation="Insufficient close history.",
            )
        sma5 = sum(closes[-5:]) / 5
        sma10 = sum(closes[-10:]) / 10
        latest_close = float(closes[-1])

        passed = latest_close > sma5 > sma10
        score_pct = Decimal(str((sma5 / sma10 - 1) * 100)) if sma10 > 0 else Decimal("0")
        return RuleResult(
            rule_id=rule_id,
            engine_id=self.engine_id,
            passed=passed,
            raw_value=Decimal(str(latest_close)),
            threshold=Decimal(str(sma5)),
            operator=">",
            weight=weight,
            contribution=weight if passed else Decimal("0"),
            explanation=(
                f"Close vs SMA5/SMA10 SMA spread {self._s(score_pct)}%: "
                f"{'Follow-through confirmed' if passed else 'No follow-through'}."
            ),
        )

    def _eval_bo_false_breakout(self, series: OHLCVSeries, rc: RuleConfig | None) -> RuleResult:
        rule_id = "bo_false_breakout"
        weight = self._weight(rc, Decimal("0.5"))
        bars = series.bars
        latest_bar = series.latest
        if latest_bar is None or not bars or len(bars) < 25:
            return RuleResult(
                rule_id=rule_id,
                engine_id=self.engine_id,
                passed=False,
                raw_value=None,
                threshold=Decimal("0"),
                operator="bool",
                weight=weight,
                contribution=Decimal("0"),
                explanation="Insufficient data for false breakout detection.",
            )
        # False breakout check: define the 20-day range midpoint as support.
        # If close is above the midpoint, it's not a false breakout.
        high_20, low_20 = self._compute_recent_range(series)
        if high_20 is None or low_20 is None:
            return RuleResult(
                rule_id=rule_id,
                engine_id=self.engine_id,
                passed=False,
                raw_value=None,
                threshold=Decimal("0"),
                operator="bool",
                weight=weight,
                contribution=Decimal("0"),
                explanation="Cannot compute 20-day range.",
            )
        midpoint = (high_20 + low_20) / Decimal("2")
        passed = latest_bar.close >= midpoint
        # Contribution proportional to how far above midpoint
        pct_above_mid = (
            (latest_bar.close - midpoint) / midpoint * Decimal("100")
            if midpoint > 0
            else Decimal("0")
        )
        normalized = min(pct_above_mid / Decimal("10"), Decimal("1"))
        contribution = weight * max(Decimal("0"), normalized)
        return RuleResult(
            rule_id=rule_id,
            engine_id=self.engine_id,
            passed=passed,
            raw_value=latest_bar.close,
            threshold=midpoint,
            operator=">=",
            weight=weight,
            contribution=contribution,
            explanation=(
                f"Close {self._s(latest_bar.close)} {'>=' if passed else '<'} "
                f"20d midpoint {self._s(midpoint)}: "
                f"{'No false breakout' if passed else 'Possible false breakout'}."
            ),
        )
