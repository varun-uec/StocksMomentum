"""Volume & Accumulation engine (liquidity gate, accumulation/distribution, breakout volume).

Evaluates volume-based liquidity and accumulation rules deterministically:
  vol_liquidity_min:   Minimum average daily turnover gate (default ₹1cr)
  vol_accumulation_days: Accumulation/distribution over lookback period
  vol_breakout_confirm: Breakout volume confirmation via relative volume

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


class VolumeAccumulationEngine:
    """Evaluates volume-based liquidity and accumulation rules."""

    engine_id = "volume_accumulation"

    def evaluate(self, ctx: EvaluationContext, cfg: EngineConfig) -> EngineResult:
        """Evaluate the configured volume/accumulation rules deterministically.

        Uses IndicatorSet fields avg_volume50 and rel_volume, along with
        OHLCV series prices/volumes to compute:
        1. vol_liquidity_min: avg_volume50 * close >= min_turnover (gate rule)
        2. vol_accumulation_days: Fraction of days where close > open over lookback
        3. vol_breakout_confirm: rel_volume >= min_rel_volume
        """
        ind = ctx.indicators
        series = ctx.series
        rule_cfg = {r.id: r for r in cfg.rules}

        def included(rule_id: str) -> bool:
            return not cfg.rules or rule_id in rule_cfg

        evaluators: dict[str, Any] = {
            "vol_liquidity_min": lambda rc: self._eval_vol_liquidity_min(
                series, ind.avg_volume50, rc
            ),
            "vol_accumulation_days": lambda rc: self._eval_vol_accumulation_days(
                series, ind.avg_volume50, rc
            ),
            "vol_breakout_confirm": lambda rc: self._eval_vol_breakout_confirm(
                ind.rel_volume, rc
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

        # The liquidity rule is a gate if configured as such; otherwise
        # passed_gate = all evaluated rules passed.
        liquidity_rule_cfg = rule_cfg.get("vol_liquidity_min")
        liquidity_result = next(
            (r for r in rule_results if r.rule_id == "vol_liquidity_min"), None
        )
        if liquidity_rule_cfg is not None and liquidity_rule_cfg.gate and liquidity_result:
            passed_gate = liquidity_result.passed
        else:
            passed_gate = all(r.passed for r in rule_results) if rule_results else False

        return EngineResult(
            engine_id=self.engine_id,
            rule_results=tuple(rule_results),
            engine_score=engine_score,
            passed_gate=passed_gate,
            metrics={
                "avg_volume50": str(ind.avg_volume50) if ind.avg_volume50 is not None else "N/A",
                "rel_volume": str(ind.rel_volume) if ind.rel_volume is not None else "N/A",
            },
        )

    # ── Rule helpers ─────────────────────────────────────────────────────────

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

    @staticmethod
    def _int_param(rc: RuleConfig | None, key: str, default: int) -> int:
        if rc is None or key not in rc.params:
            return default
        return int(rc.params[key])

    def _eval_vol_liquidity_min(
        self, series: OHLCVSeries, avg_volume50: Decimal | None, rc: RuleConfig | None
    ) -> RuleResult:
        rule_id = "vol_liquidity_min"
        weight = self._weight(rc, Decimal("1.0"))
        min_turnover = self._param(rc, "min_turnover_inr", Decimal("10_000_000"))

        latest_bar = series.latest
        if latest_bar is None or avg_volume50 is None:
            return RuleResult(
                rule_id=rule_id,
                engine_id=self.engine_id,
                passed=False,
                raw_value=None,
                threshold=min_turnover,
                operator=">=",
                weight=weight,
                contribution=Decimal("0"),
                explanation="Insufficient data: latest bar or avg_volume50 is None.",
            )
        # Estimate daily turnover = avg_volume50 * latest_close (absolute INR)
        turnover = avg_volume50 * latest_bar.close
        passed = turnover >= min_turnover
        # Normalized contribution: clamp(turnover / min_turnover, 0, 1)
        ratio = min(turnover / min_turnover, Decimal("1")) if min_turnover > 0 else Decimal("0")
        _crore = Decimal("10000000")
        return RuleResult(
            rule_id=rule_id,
            engine_id=self.engine_id,
            passed=passed,
            raw_value=turnover,
            threshold=min_turnover,
            operator=">=",
            weight=weight,
            contribution=weight * ratio,
            explanation=(
                f"Est. daily turnover ₹{self._s(turnover / _crore)} crore "
                f"{'>=' if passed else '<'} min ₹{self._s(min_turnover / _crore)} crore."
            ),
        )

    def _eval_vol_accumulation_days(
        self,
        series: OHLCVSeries,
        avg_volume50: Decimal | None,
        rc: RuleConfig | None,
    ) -> RuleResult:
        """Evaluate net accumulation over the lookback window.

        Accumulation day: close > open AND volume > avg_volume (institutional buying).
        Distribution day: close < open AND volume > avg_volume (institutional selling).
        Net = accumulation_days - distribution_days must be positive for bullish bias.

        When avg_volume50 is unavailable, falls back to counting all up-days
        (close > open) regardless of volume — a simplified proxy.
        """
        rule_id = "vol_accumulation_days"
        weight = self._weight(rc, Decimal("1.0"))
        lookback = self._int_param(rc, "lookback", 25)

        bars = series.bars
        if not bars or len(bars) < lookback:
            return RuleResult(
                rule_id=rule_id,
                engine_id=self.engine_id,
                passed=False,
                raw_value=None,
                threshold=Decimal(str(lookback)),
                operator="bool",
                weight=weight,
                contribution=Decimal("0"),
                explanation=(
                    f"Insufficient history: need {lookback} bars, "
                    f"got {len(bars) if bars else 0}."
                ),
            )

        recent = bars[-lookback:]
        avg_vol_float = float(avg_volume50) if avg_volume50 is not None else None

        if avg_vol_float is not None and avg_vol_float > 0:
            # True accumulation/distribution: requires above-average volume
            accumulation_days = sum(
                1 for b in recent
                if b.close > b.open and b.volume > avg_vol_float
            )
            distribution_days = sum(
                1 for b in recent
                if b.close < b.open and b.volume > avg_vol_float
            )
            net = accumulation_days - distribution_days
            passed = net > 0
            ratio = Decimal(str(max(0, net))) / Decimal(str(lookback))
            explanation = (
                f"Net accumulation {net:+d} ({accumulation_days} accum, "
                f"{distribution_days} distrib over {lookback}d on above-avg volume): "
                f"{'Bullish' if passed else 'Neutral/Bearish'} institutional bias."
            )
        else:
            # Fallback: count all up-days (no volume qualification)
            accumulation_days = sum(1 for b in recent if b.close > b.open)
            net = accumulation_days - (lookback - accumulation_days)
            passed = accumulation_days > (lookback // 2)
            ratio = Decimal(str(accumulation_days)) / Decimal(str(lookback))
            explanation = (
                f"Up-days {accumulation_days}/{lookback} (avg volume unavailable — "
                f"simplified proxy): {'Bullish' if passed else 'Neutral/Bearish'}."
            )

        return RuleResult(
            rule_id=rule_id,
            engine_id=self.engine_id,
            passed=passed,
            raw_value=Decimal(str(net)),
            threshold=Decimal("0"),
            operator=">",
            weight=weight,
            contribution=weight if passed else weight * ratio,
            explanation=explanation,
        )

    def _eval_vol_breakout_confirm(
        self, rel_volume: Decimal | None, rc: RuleConfig | None
    ) -> RuleResult:
        rule_id = "vol_breakout_confirm"
        weight = self._weight(rc, Decimal("1.0"))
        min_rel_volume = self._param(rc, "min_rel_volume", Decimal("1.4"))

        if rel_volume is None:
            return RuleResult(
                rule_id=rule_id,
                engine_id=self.engine_id,
                passed=False,
                raw_value=None,
                threshold=min_rel_volume,
                operator=">=",
                weight=weight,
                contribution=Decimal("0"),
                explanation="Relative volume unavailable — insufficient volume history.",
            )
        passed = rel_volume >= min_rel_volume
        # Normalized contribution: clamp(rel_volume / min_rel_volume, 0, 1)
        normalized = (
            min(rel_volume / min_rel_volume, Decimal("1")) if min_rel_volume > 0 else Decimal("0")
        )
        contribution = weight * normalized
        return RuleResult(
            rule_id=rule_id,
            engine_id=self.engine_id,
            passed=passed,
            raw_value=rel_volume,
            threshold=min_rel_volume,
            operator=">=",
            weight=weight,
            contribution=contribution,
            explanation=(
                f"Relative volume {self._s(rel_volume)}x {'>=' if passed else '<'} "
                f"min {self._s(min_rel_volume)}x."
            ),
        )
