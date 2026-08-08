"""Risk Assessment engine (ATR, extension, stop quality, risk-reward).

Evaluates risk and position-characteristic rules deterministically:
  risk_extension:   Price extension from key moving average (overbought check)
  risk_atr:         Volatility check via ADR% (Average Daily Range)
  risk_rr:          Risk-reward ratio estimate

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
from momentum25.domain.research.swing_targets import compute_swing_target_plan
from momentum25.domain.value_objects.results import EngineResult, RuleResult


class RiskEngine:
    """Evaluates risk and position-characteristic rules."""

    engine_id = "risk"

    def evaluate(self, ctx: EvaluationContext, cfg: EngineConfig) -> EngineResult:
        """Evaluate the configured risk rules deterministically.

        Uses IndicatorSet and OHLCV series to compute:
        1. risk_extension: How far price has extended above SMA(50) — overbought check.
        2. risk_atr: Volatility check via ADR% (Average Daily Range %).
        3. risk_rr: Risk-reward ratio estimate using ATR-based stop.
        """
        ind = ctx.indicators
        series = ctx.series
        rule_cfg = {r.id: r for r in cfg.rules}

        def included(rule_id: str) -> bool:
            return not cfg.rules or rule_id in rule_cfg

        evaluators: dict[str, Any] = {
            "risk_extension": lambda rc: self._eval_risk_extension(series, ind.sma50, rc),
            "risk_atr": lambda rc: self._eval_risk_atr(ind.adr_pct, rc),
            "risk_rr": lambda rc: self._eval_risk_rr(
                series, ind.atr14, ind.swing_resistance, rc
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
            passed_gate=False,  # Risk is not a gate engine
            metrics={
                "adr_pct": str(ind.adr_pct) if ind.adr_pct is not None else "N/A",
                "atr14": str(ind.atr14) if ind.atr14 is not None else "N/A",
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

    def _eval_risk_extension(
        self, series: OHLCVSeries, sma_ma: Decimal | None, rc: RuleConfig | None
    ) -> RuleResult:
        rule_id = "risk_extension"
        weight = self._weight(rc, Decimal("1.0"))
        ma_period = self._int_param(rc, "ma", 50)
        max_ext_pct = self._param(rc, "max_pct", Decimal("25"))

        latest_bar = series.latest
        if latest_bar is None:
            return RuleResult(
                rule_id=rule_id,
                engine_id=self.engine_id,
                passed=False,
                raw_value=None,
                threshold=max_ext_pct,
                operator="<=",
                weight=weight,
                contribution=Decimal("0"),
                explanation="Insufficient data: latest bar is None.",
            )

        # Use the pre-computed SMA from IndicatorSet if available
        ma_value = sma_ma
        if ma_value is None:
            # Fall back to computing SMA from series
            bars = series.bars
            if not bars or len(bars) < ma_period:
                return RuleResult(
                    rule_id=rule_id,
                    engine_id=self.engine_id,
                    passed=False,
                    raw_value=None,
                    threshold=max_ext_pct,
                    operator="<=",
                    weight=weight,
                    contribution=Decimal("0"),
                    explanation=f"Insufficient data: need {ma_period} bars for SMA{ma_period}.",
                )
            closes = [float(b.close) for b in bars]
            ma_value = Decimal(str(sum(closes[-ma_period:]) / ma_period))

        if ma_value == 0:
            return RuleResult(
                rule_id=rule_id,
                engine_id=self.engine_id,
                passed=False,
                raw_value=Decimal("0"),
                threshold=max_ext_pct,
                operator="<=",
                weight=weight,
                contribution=Decimal("0"),
                explanation="Cannot compute extension: MA value is zero.",
            )

        ext_pct = ((latest_bar.close - ma_value) / ma_value) * Decimal("100")
        passed = ext_pct <= max_ext_pct
        # Normalized contribution: 1 - (ext / max_ext) clamped to [0, 1]
        normalized = (
            max(Decimal("0"), Decimal("1") - (ext_pct / max_ext_pct))
            if max_ext_pct > 0
            else Decimal("0")
        )
        return RuleResult(
            rule_id=rule_id,
            engine_id=self.engine_id,
            passed=passed,
            raw_value=ext_pct,
            threshold=max_ext_pct,
            operator="<=",
            weight=weight,
            contribution=weight * normalized,
            explanation=(
                f"Price extended {self._s(ext_pct)}% above SMA{ma_period} "
                f"({'Within range' if passed else 'Overextended'}, max {self._s(max_ext_pct)}%)."
            ),
        )

    def _eval_risk_atr(self, adr_pct: Decimal | None, rc: RuleConfig | None) -> RuleResult:
        rule_id = "risk_atr"
        weight = self._weight(rc, Decimal("0.5"))
        max_adr_pct = self._param(rc, "max_adr_pct", Decimal("8"))

        if adr_pct is None:
            return RuleResult(
                rule_id=rule_id,
                engine_id=self.engine_id,
                passed=False,
                raw_value=None,
                threshold=max_adr_pct,
                operator="<=",
                weight=weight,
                contribution=Decimal("0"),
                explanation="ADR% unavailable — insufficient data.",
            )
        passed = adr_pct <= max_adr_pct
        # Normalized contribution: 1 - (adr / max_adr) clamped to [0, 1]
        normalized = (
            max(Decimal("0"), Decimal("1") - (adr_pct / max_adr_pct))
            if max_adr_pct > 0
            else Decimal("0")
        )
        contribution = weight * normalized
        return RuleResult(
            rule_id=rule_id,
            engine_id=self.engine_id,
            passed=passed,
            raw_value=adr_pct,
            threshold=max_adr_pct,
            operator="<=",
            weight=weight,
            contribution=contribution,
            explanation=(
                f"ADR% {self._s(adr_pct)}% {'<=' if passed else '>'} "
                f"max {self._s(max_adr_pct)}%: "
                f"{'Acceptable volatility' if passed else 'Excessive volatility'}."
            ),
        )

    def _eval_risk_rr(
        self,
        series: OHLCVSeries,
        atr14: Decimal | None,
        swing_resistance: Decimal | None,
        rc: RuleConfig | None,
    ) -> RuleResult:
        """Risk-reward ratio via :func:`compute_swing_target_plan` (Phase 3.1/3.2).

        Previously reward was ``max(high, last 20 bars) - close``, which always
        includes the signal bar itself: a stock making a new 20-day high on the
        signal date -- exactly the breakout population this system selects --
        had reward collapse to near zero, failing the rule almost by
        construction. Reward is now the distance to the nearest *confirmed*
        swing-high pivot above price (Phase 2.3), falling back to an
        ATR-multiple projection when no such pivot exists (the common case for
        a genuine breakout at a new high) -- see ``domain.research.swing_targets``
        for the full rationale and default multiples.
        """
        rule_id = "risk_rr"
        weight = self._weight(rc, Decimal("1.0"))
        min_rr_ratio = self._param(rc, "min_ratio", Decimal("2.0"))

        latest_bar = series.latest
        if latest_bar is None:
            return RuleResult(
                rule_id=rule_id,
                engine_id=self.engine_id,
                passed=False,
                raw_value=None,
                threshold=min_rr_ratio,
                operator=">=",
                weight=weight,
                contribution=Decimal("0"),
                explanation="Insufficient data: latest bar is None.",
            )

        plan = compute_swing_target_plan(latest_bar.close, atr14, swing_resistance)
        if plan is None:
            return RuleResult(
                rule_id=rule_id,
                engine_id=self.engine_id,
                passed=False,
                raw_value=Decimal("0"),
                threshold=min_rr_ratio,
                operator=">=",
                weight=weight,
                contribution=Decimal("0"),
                explanation="Risk estimate is zero or negative.",
            )

        rr_ratio = plan.rr_ratio
        passed = rr_ratio >= min_rr_ratio
        # Normalized contribution: clamp(rr / (min_rr * 2), 0, 1)
        normalized = (
            min(rr_ratio / (min_rr_ratio * Decimal("2")), Decimal("1"))
            if min_rr_ratio > 0
            else Decimal("0")
        )
        return RuleResult(
            rule_id=rule_id,
            engine_id=self.engine_id,
            passed=passed,
            raw_value=rr_ratio,
            threshold=min_rr_ratio,
            operator=">=",
            weight=weight,
            contribution=weight * normalized,
            explanation=(
                f"Risk-reward ratio {self._s(rr_ratio)}:1 "
                f"{'>=' if passed else '<'} min {self._s(min_rr_ratio)}:1 "
                f"(target via {plan.target_basis}; "
                f"{'Favorable' if passed else 'Unfavorable'})."
            ),
        )
