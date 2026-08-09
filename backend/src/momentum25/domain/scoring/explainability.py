"""Explainability builder — constructs deterministic, human-readable rationale.

Produces structured explanations at rule, engine, and portfolio levels.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal

from momentum25.domain.value_objects.results import EngineResult, Ranking, RuleResult, StockScore

# Maps the 8 real TrendTemplateEngine rule ids to the dashboard's checklist slots.
_TREND_TEMPLATE_CHECKLIST_MAP: dict[str, str] = {
    "tt_close_above_sma150_200": "price_above_long_mas",
    "tt_sma150_above_sma200": "ma150_above_ma200",
    "tt_sma200_uptrend": "ma200_trending_up",
    "tt_sma_stack": "ma50_alignment",
    "tt_close_above_sma50": "price_above_ma50",
    "tt_above_52w_low": "above_52w_low_30pct",
    "tt_near_52w_high": "within_52w_high_25pct",
    "tt_rs_rating_min": "rs_rating_gte_70",
}

# Plain-English label for each rule id, for prose meant to be read by a human.
# The rule ids themselves are stable identifiers for the structured payload and
# must not leak into rationale copy.
_RULE_LABELS: dict[str, str] = {
    "tt_close_above_sma150_200": "close above the 150- and 200-day averages",
    "tt_close_above_sma50": "close above the 50-day average",
    "tt_above_52w_low": "well clear of the 52-week low",
    "tt_near_52w_high": "close to the 52-week high",
    "tt_sma150_above_sma200": "150-day average above the 200-day",
    "tt_sma200_uptrend": "200-day average trending up",
    "tt_sma_stack": "50-day average above the 150- and 200-day",
    "tt_rs_rating_min": "relative-strength rating above the minimum",
    "rs_rating": "relative-strength rating",
    "rs_trend": "relative strength improving",
    "rs_line_slope": "relative-strength line sloping up",
    "rs_line_uptrend": "relative-strength line in an uptrend",
    "rs_sector_relative": "outperforming its sector",
    "rs_industry_relative": "outperforming its industry",
    "bo_pivot_breakout": "breaking out of its recent range",
    "bo_followthrough": "follow-through after the breakout",
    "bo_false_breakout": "no false-breakout reversal",
    "vol_liquidity_min": "minimum traded liquidity",
    "vol_accumulation_days": "volume accumulation days",
    "vol_breakout_confirm": "volume confirming the breakout",
    "risk_extension": "not overextended from its average",
    "risk_atr": "volatility within range",
    "risk_rr": "acceptable risk profile",
}

# How many failed conditions to name before summarising the remainder.
_MAX_NAMED_FAILURES = 3


def _rule_label(rule_id: str) -> str:
    """Return the human label for *rule_id*, falling back to a readable form."""
    return _RULE_LABELS.get(rule_id, rule_id.split("_", 1)[-1].replace("_", " "))


def _join(labels: list[str]) -> str:
    """Join labels as an English list ("a", "a and b", "a, b and c")."""
    if len(labels) == 1:
        return labels[0]
    return f"{', '.join(labels[:-1])} and {labels[-1]}"


def _summarise(results: list[RuleResult]) -> str:
    """Name the first few failed conditions in English and count the rest."""
    named = [_rule_label(r.rule_id) for r in results[:_MAX_NAMED_FAILURES]]
    remainder = len(results) - len(named)
    text = _join(named)
    if remainder:
        text += f", plus {remainder} other{'s' if remainder > 1 else ''}"
    return text


# risk engine: bucket by count of failed risk rules (risk_extension, risk_atr, risk_rr).
_RISK_BUCKET_BY_FAILURES = {0: "Low", 1: "Medium"}

# breakout engine: bo_pivot_breakout's own pass threshold is 70% of the 20d range.
_BREAKOUT_STRONG_PCT = Decimal("90")
_BREAKOUT_MODERATE_PCT = Decimal("70")


@dataclass(frozen=True, slots=True)
class RuleExplanation:
    """Human-readable explanation for a single rule evaluation."""

    rule_id: str
    engine_name: str
    passed: bool
    explanation: str
    threshold: str | None = None
    actual_value: str | None = None
    contribution: Decimal = Decimal("0")


@dataclass(frozen=True, slots=True)
class EngineExplanation:
    """Summary explanation for an engine's aggregate evaluation."""

    engine_name: str
    passed: bool
    score: Decimal
    weight: Decimal
    contribution: Decimal
    rule_count: int
    rules_passed: int
    rules_failed: int
    summary: str


@dataclass(frozen=True, slots=True)
class StockExplanation:
    """Complete explainability payload for one stock in a screening run."""

    symbol: str
    security_id: int
    overall_passed: bool
    momentum_score: Decimal
    buy_setup_score: Decimal
    composite_score: Decimal
    rank: int | None = None
    percentile: int | None = None
    rule_explanations: tuple[RuleExplanation, ...] = field(default_factory=tuple)
    engine_explanations: tuple[EngineExplanation, ...] = field(default_factory=tuple)
    hard_filter_failures: tuple[str, ...] = field(default_factory=tuple)
    overall_rationale: str = ""


class ExplainabilityBuilderImpl:
    """Builds deterministic, structured explanations from screening results."""

    def build_rationale(self, stock_score: StockScore, rule_results: list[RuleResult]) -> str:
        """Build a concise human-readable rationale for a stock.

        This is prose shown to a person, so it carries plain-English condition
        names and one-decimal scores -- never raw rule ids or full-precision
        Decimals. The structured ``rule_explanations`` payload remains the place
        to read exact identifiers and values from.
        """
        momentum = stock_score.momentum_score.quantize(Decimal("0.1"))
        buy_setup = stock_score.buy_setup_score.quantize(Decimal("0.1"))
        parts: list[str] = [
            f"Momentum scores {momentum} and buy-setup {buy_setup} out of 100."
        ]

        passed = [r for r in rule_results if r.passed]
        failed = [r for r in rule_results if not r.passed]
        total = len(rule_results)
        if total:
            parts.append(f"{len(passed)} of {total} conditions met.")

        # Gate failures are the reason it does not qualify, so they lead and the
        # remaining failures are reported separately rather than twice over.
        blocking = [r for r in failed if self._is_hard_filter(r)]
        other = [r for r in failed if r not in blocking]

        if blocking:
            parts.append(f"It is blocked by the hard gate on {_summarise(blocking)}.")
        elif stock_score.hard_filters_passed:
            parts.append("It clears every hard gate.")
        else:
            parts.append("It does not clear the hard gates.")

        if other:
            parts.append(f"Also unmet: {_summarise(other)}.")

        return " ".join(parts)

    def build_explanation(
        self, stock_score: StockScore, rule_results: list[RuleResult]
    ) -> StockExplanation:
        """Build a complete structured explanation for one stock."""
        rule_explanations = self._build_rule_explanations(rule_results)
        engine_explanations = self._build_engine_explanations(stock_score, rule_results)
        hard_failures = tuple(
            r.rule_id for r in rule_results if not r.passed and self._is_hard_filter(r)
        )
        overall_rationale = self.build_rationale(stock_score, rule_results)

        return StockExplanation(
            symbol="",
            security_id=stock_score.security_id,
            overall_passed=stock_score.hard_filters_passed,
            momentum_score=stock_score.momentum_score,
            buy_setup_score=stock_score.buy_setup_score,
            composite_score=stock_score.momentum_score,
            rank=None,
            percentile=None,
            rule_explanations=rule_explanations,
            engine_explanations=engine_explanations,
            hard_filter_failures=hard_failures,
            overall_rationale=overall_rationale,
        )

    def _build_rule_explanations(
        self, rule_results: list[RuleResult]
    ) -> tuple[RuleExplanation, ...]:
        """Convert raw RuleResults into human-readable explanations."""
        return tuple(
            RuleExplanation(
                rule_id=r.rule_id,
                engine_name=r.engine_id,
                passed=r.passed,
                explanation=r.explanation,
                threshold=str(r.threshold) if r.threshold is not None else None,
                actual_value=str(r.raw_value) if r.raw_value is not None else None,
                contribution=r.contribution,
            )
            for r in rule_results
        )

    def _build_engine_explanations(
        self, stock_score: StockScore, rule_results: list[RuleResult]
    ) -> tuple[EngineExplanation, ...]:
        """Aggregate rule results into engine-level summaries."""
        engine_rules: dict[str, list[RuleResult]] = {}
        for r in rule_results:
            engine_rules.setdefault(r.engine_id, []).append(r)

        explanations = []
        for engine_name, rules in engine_rules.items():
            passed_count = sum(1 for r in rules if r.passed)
            failed_count = len(rules) - passed_count
            engine_passed = all(r.passed for r in rules)
            engine_result = next(
                (e for e in stock_score.engine_results if e.engine_id == engine_name), None
            )
            score = engine_result.engine_score if engine_result else Decimal("0")
            weight = sum((r.weight for r in rules), Decimal("0"))
            contribution = sum((r.contribution for r in rules), Decimal("0"))

            summary = (
                f"Engine '{engine_name}': {passed_count}/{len(rules)} rules passed. "
                f"Score={score}, weight={weight}, contribution={contribution}."
            )

            explanations.append(
                EngineExplanation(
                    engine_name=engine_name,
                    passed=engine_passed,
                    score=score,
                    weight=weight,
                    contribution=contribution,
                    rule_count=len(rules),
                    rules_passed=passed_count,
                    rules_failed=failed_count,
                    summary=summary,
                )
            )
        return tuple(explanations)

    @staticmethod
    def _is_hard_filter(rule_result: RuleResult) -> bool:
        """Determine if a rule is a hard filter (blocking) based on metadata."""
        return rule_result.engine_id in {"trend_template", "risk"} and not rule_result.passed

    def build_historical_explanation(
        self,
        run_id: int,
        security_id: int,
        rule_results: list[RuleResult],
        ranking: Ranking | None = None,
    ) -> StockExplanation:
        """Build immutable explanation for a historical run snapshot.

        Produces the same output as `build_explanation` for the given persisted
        rule results, ensuring historical reproducibility.

        Args:
            run_id: The screening run this snapshot belongs to.
            security_id: The security being explained.
            rule_results: All persisted rule results for this security in this run.
            ranking: The security's persisted :class:`Ranking` for this run
                (momentum/buy-setup score and rank as actually computed by
                :class:`ScoringEngineImpl`/:class:`RankingEngineImpl`). When
                omitted, momentum/buy-setup score fall back to a naive
                unweighted sum of engine scores and rank is unavailable --
                callers that have the persisted ranking should always pass it
                so the explanation matches the number the user is looking at.
        """
        from momentum25.domain.value_objects.results import StockScore as DomainStockScore

        engine_rules: dict[str, list[RuleResult]] = {}
        for r in rule_results:
            engine_rules.setdefault(r.engine_id, []).append(r)

        engine_results = []
        for engine_id, rules in engine_rules.items():
            contrib = sum((r.contribution for r in rules), Decimal("0"))
            engine_results.append(
                EngineResult(
                    engine_id=engine_id,
                    rule_results=tuple(rules),
                    engine_score=contrib,
                    passed_gate=all(r.passed for r in rules),
                )
            )

        if ranking is not None:
            momentum_score = ranking.momentum_score
            buy_setup_score = ranking.buy_setup_score
            hard_filters_passed = ranking.rank is not None
        else:
            momentum_score = sum((e.engine_score for e in engine_results), Decimal("0"))
            buy_setup_score = Decimal("0")
            hard_filters_passed = all(r.passed for r in rule_results)

        stock_score = DomainStockScore(
            security_id=security_id,
            momentum_score=momentum_score,
            buy_setup_score=buy_setup_score,
            engine_results=tuple(engine_results),
            hard_filters_passed=hard_filters_passed,
        )

        explanation = self.build_explanation(stock_score, rule_results)
        if ranking is not None and ranking.rank is not None:
            explanation = replace(explanation, rank=ranking.rank)
        return explanation

    def build_dashboard_summary(self, rule_results: list[RuleResult]) -> dict[str, object]:
        """Build the compact per-row summary the dashboard table renders.

        Every field is derived deterministically from already-computed rule
        results -- no new thresholds are invented beyond what each engine
        already uses to decide pass/fail:

        - ``checklist``: the 8 real Trend Template rules, keyed by dashboard slot.
        - ``risk``: bucketed by how many of the 3 risk-engine rules failed.
        - ``volume``: bucketed by how many of the 2 volume-confirmation rules passed.
        - ``breakout``: bucketed by ``bo_pivot_breakout``'s own distance-to-pivot
          value, using its own pass threshold (70%) as the "Moderate" floor and
          90% (comfortably clear of it) as the "Strong" floor.
        - ``pattern``: the highest-quality detected chart pattern, if any.
        """
        by_id = {r.rule_id: r for r in rule_results}

        checklist: dict[str, bool] | None = None
        if any(rid in by_id for rid in _TREND_TEMPLATE_CHECKLIST_MAP):
            checklist = {
                slot: by_id[rid].passed
                for rid, slot in _TREND_TEMPLATE_CHECKLIST_MAP.items()
                if rid in by_id
            }

        risk_rules = [by_id[r] for r in ("risk_extension", "risk_atr", "risk_rr") if r in by_id]
        risk_bucket = None
        if risk_rules:
            failed = sum(1 for r in risk_rules if not r.passed)
            risk_bucket = _RISK_BUCKET_BY_FAILURES.get(failed, "High")

        vol_rules = [
            by_id[r] for r in ("vol_breakout_confirm", "vol_accumulation_days") if r in by_id
        ]
        volume_bucket = None
        if vol_rules:
            passed = sum(1 for r in vol_rules if r.passed)
            volume_bucket = {0: "Low", 1: "Medium"}.get(passed, "High")

        breakout_bucket = None
        if "bo_pivot_breakout" in by_id:
            pct = by_id["bo_pivot_breakout"].raw_value
            if pct is None:
                breakout_bucket = None
            elif pct >= _BREAKOUT_STRONG_PCT:
                breakout_bucket = "Strong"
            elif pct >= _BREAKOUT_MODERATE_PCT:
                breakout_bucket = "Moderate"
            else:
                breakout_bucket = "Weak"

        pattern_rules = [
            r for r in rule_results if r.rule_id.startswith("pattern_") and r.passed
        ]
        pattern_name = None
        if pattern_rules:
            best = max(pattern_rules, key=lambda r: r.raw_value or Decimal("0"))
            pattern_name = best.rule_id.removeprefix("pattern_").replace("_", " ").title()

        rs_rating: int | None = None
        if "tt_rs_rating_min" in by_id and by_id["tt_rs_rating_min"].raw_value is not None:
            rs_rating = int(by_id["tt_rs_rating_min"].raw_value)

        return {
            "checklist": checklist,
            "risk": risk_bucket,
            "volume": volume_bucket,
            "breakout": breakout_bucket,
            "pattern": pattern_name,
            "rs_rating": rs_rating,
        }