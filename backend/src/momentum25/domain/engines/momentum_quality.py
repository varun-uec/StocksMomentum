"""Momentum Quality engine (trend persistence, acceleration, MTF confirmation).

Evaluates momentum quality and sustainability rules deterministically:
  mq_trend_persistence:  Trend persistence — price consistently above key MA over lookback
  mq_acceleration:       Momentum acceleration — recent return vs longer-term return

Rule inclusion, weight, and params come from ``cfg.rules`` (ADR-005
strategy-as-config), matched by rule id rather than list position: a rule
runs only if ``cfg.rules`` is empty (the "evaluate everything" default) or
its id appears in ``cfg.rules``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from momentum25.domain.engines.base import EvaluationContext
from momentum25.domain.entities.market_data import OHLCVSeries
from momentum25.domain.entities.strategy import EngineConfig, RuleConfig
from momentum25.domain.value_objects.results import EngineResult, RuleResult


class MomentumQualityEngine:
    """Evaluates momentum quality and sustainability rules."""

    engine_id = "momentum_quality"

    def evaluate(self, ctx: EvaluationContext, cfg: EngineConfig) -> EngineResult:
        """Evaluate the configured momentum-quality rules deterministically.

        Uses OHLCV series to compute:
        1. mq_trend_persistence: Fraction of days where close > configurable MA
           over the lookback period (e.g., 63 sessions / ~3 months).
        2. mq_acceleration: Momentum acceleration — compares recent return (20d)
           to longer-term return (63d) to see if momentum is building.
        """
        series = ctx.series
        rule_cfg = {r.id: r for r in cfg.rules}

        def included(rule_id: str) -> bool:
            return not cfg.rules or rule_id in rule_cfg

        evaluators: dict[str, Any] = {
            "mq_trend_persistence": lambda rc: self._eval_mq_trend_persistence(series, rc),
            "mq_acceleration": lambda rc: self._eval_mq_acceleration(series, rc),
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
            passed_gate=False,  # Not a gate engine
        )

    # ── Rule helpers ─────────────────────────────────────────────────────────

    def _s(self, val: Decimal | None) -> str:
        return f"{val:.4f}" if val is not None else "N/A"

    @staticmethod
    def _weight(rc: RuleConfig | None, default: Decimal) -> Decimal:
        return rc.weight if rc is not None else default

    @staticmethod
    def _int_param(rc: RuleConfig | None, key: str, default: int) -> int:
        if rc is None or key not in rc.params:
            return default
        return int(rc.params[key])

    def _compute_sma(self, closes: list[float], period: int) -> float | None:
        """Compute SMA for last `period` values."""
        if len(closes) < period:
            return None
        return sum(closes[-period:]) / period

    def _compute_pct_return(self, closes: list[float], periods_ago: int) -> Decimal | None:
        """Return percentage return over `periods_ago` bars."""
        if len(closes) < periods_ago + 1:
            return None
        latest = closes[-1]
        prior = closes[-1 - periods_ago]
        if prior == 0:
            return None
        return Decimal(str((latest / prior - 1) * 100))

    def _eval_mq_trend_persistence(
        self, series: OHLCVSeries, rc: RuleConfig | None
    ) -> RuleResult:
        rule_id = "mq_trend_persistence"
        weight = self._weight(rc, Decimal("1.0"))
        ma_period = self._int_param(rc, "ma", 50)
        lookback = self._int_param(rc, "lookback", 63)
        bars = series.bars
        # Only the empty case needs its own branch. A short-but-non-empty series
        # falls through to the length check below, which reports the same
        # failure with the actual bar count.
        if not bars:
            return RuleResult(
                rule_id=rule_id,
                engine_id=self.engine_id,
                passed=False,
                raw_value=None,
                threshold=Decimal("0"),
                operator=">=",
                weight=weight,
                contribution=Decimal("0"),
                explanation="Insufficient data for trend persistence.",
            )

        closes = [float(b.close) for b in bars]
        if len(closes) < lookback + ma_period:
            return RuleResult(
                rule_id=rule_id,
                engine_id=self.engine_id,
                passed=False,
                raw_value=Decimal(str(len(closes))),
                threshold=Decimal(str(lookback + ma_period)),
                operator=">=",
                weight=weight,
                contribution=Decimal("0"),
                explanation=(
                    f"Insufficient history: need {lookback + ma_period} bars, "
                    f"got {len(closes)}."
                ),
            )

        # Days where close > SMA(ma) over the lookback window.
        #
        # Numerator and denominator must count the *same* population. Slicing
        # `lookback + ma_period` bars leaves `lookback + 1` bars with a full SMA
        # window while the denominator caps at `lookback`, which reported ratios
        # above 1 (observed: "64/63 days (101.6%)") and inflated `contribution`
        # for every partially-passing security. The window is now the final
        # `valid_days` bars, taken identically on both sides.
        lookback_closes = closes[-lookback - ma_period:]
        valid_days = min(lookback, len(lookback_closes) - ma_period + 1)
        persistence_count = 0
        for i in range(len(lookback_closes) - valid_days, len(lookback_closes)):
            sma = sum(lookback_closes[i - ma_period + 1:i + 1]) / ma_period
            if lookback_closes[i] > sma:
                persistence_count += 1

        ratio = (
            Decimal(str(persistence_count)) / Decimal(str(valid_days))
            if valid_days > 0
            else Decimal("0")
        )
        assert Decimal("0") <= ratio <= Decimal("1"), (
            f"mq_trend_persistence ratio out of range: "
            f"{persistence_count}/{valid_days} = {ratio}"
        )

        # Pass if price is above the MA at least 60% of days
        passed = ratio >= Decimal("0.6")
        return RuleResult(
            rule_id=rule_id,
            engine_id=self.engine_id,
            passed=passed,
            raw_value=ratio * Decimal("100"),
            threshold=Decimal("60"),
            operator=">=",
            weight=weight,
            contribution=weight if passed else weight * ratio,
            explanation=(
                f"Price above SMA{ma_period} on {persistence_count}/{valid_days} days "
                f"({self._s(ratio * Decimal('100'))}%): "
                f"{'Persistent trend' if passed else 'Weak trend persistence'}."
            ),
        )

    def _eval_mq_acceleration(self, series: OHLCVSeries, rc: RuleConfig | None) -> RuleResult:
        rule_id = "mq_acceleration"
        weight = self._weight(rc, Decimal("1.0"))
        bars = series.bars
        if not bars or len(bars) < 63:
            return RuleResult(
                rule_id=rule_id,
                engine_id=self.engine_id,
                passed=False,
                raw_value=None,
                threshold=Decimal("0"),
                operator=">",
                weight=weight,
                contribution=Decimal("0"),
                explanation="Insufficient data for momentum acceleration (need 63+ bars).",
            )

        closes = [float(b.close) for b in bars]

        ret_20 = self._compute_pct_return(closes, 20)
        ret_63 = self._compute_pct_return(closes, 63)

        if ret_20 is None or ret_63 is None:
            return RuleResult(
                rule_id=rule_id,
                engine_id=self.engine_id,
                passed=False,
                raw_value=None,
                threshold=Decimal("0"),
                operator=">",
                weight=weight,
                contribution=Decimal("0"),
                explanation="Cannot compute returns for acceleration check.",
            )

        # Acceleration: recent return > longer-term return (momentum building)
        # Also require ret_20 > 0 to confirm positive direction
        passed = ret_20 > ret_63 and ret_20 > Decimal("0")
        acceleration = ret_20 - ret_63
        # Normalized contribution: dampened sigmoid-like
        normalized = (
            min(abs(acceleration) / Decimal("20"), Decimal("1")) if passed else Decimal("0")
        )
        return RuleResult(
            rule_id=rule_id,
            engine_id=self.engine_id,
            passed=passed,
            raw_value=ret_20,
            threshold=ret_63,
            operator=">",
            weight=weight,
            contribution=weight * normalized,
            explanation=(
                f"20d return {self._s(ret_20)}% vs 63d return {self._s(ret_63)}%: "
                f"{'Accelerating' if passed else 'Decelerating/Neutral'} momentum."
            ),
        )