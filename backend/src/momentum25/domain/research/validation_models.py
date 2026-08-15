"""Domain models for Strategy Validation & Alpha Research (Phase 6).

All types are immutable, deterministic, and carry no I/O dependencies.
Extends the Phase 4 research models with alpha measurement, benchmark
comparison, scorecards, and historical validation capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

# ═══════════════════════════════════════════════════════════════════════════════
# Measurability — "not measured" is not the same claim as "measured zero"
# ═══════════════════════════════════════════════════════════════════════════════

# Reasons a performance metric cannot be computed. Stable identifiers: the UI
# keys copy off them.
NO_FORWARD_RETURNS = "no_forward_returns"
NO_RUNS = "no_runs"


@dataclass(frozen=True, slots=True)
class Measurability:
    """Whether a report's return-derived metrics could be computed at all.

    Every performance metric on this platform is a function of realised
    forward returns. When ``forward_returns`` holds no matured row for the
    analysed runs, those metrics are ``None`` and this block says why —
    rather than emitting ``0`` and letting a reader mistake "never measured"
    for "measured, and it earned nothing". Follows the ``"no_returns"``
    convention ``/validation/alpha`` already used.
    """

    forward_returns_available: bool
    reason: str | None = None


MEASURABLE = Measurability(forward_returns_available=True)
_MEASURABLE = MEASURABLE  # module-internal alias for default field values


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 1 — Historical Validation
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class ValidationWindow:
    """A configurable historical validation window."""

    label: str  # "1Y", "3Y", "5Y", "10Y"
    start_date: date
    end_date: date
    trading_days: int


@dataclass(frozen=True, slots=True)
class HistoricalValidationResult:
    """Result of running the screening engine across a validation window.

    For every trading day in the window, the complete screening pipeline
    is executed and the Top 25 rankings are persisted with all scores,
    rule evaluations, and explanations.
    """

    strategy_name: str
    window: ValidationWindow
    total_runs: int
    successful_runs: int
    failed_runs: int
    run_ids: tuple[int, ...]
    summary: dict[str, Any]


@dataclass(frozen=True, slots=True)
class HistoricalValidationReport:
    """Complete report across all validation windows for a strategy."""

    strategy_name: str
    strategy_id: int
    windows: tuple[HistoricalValidationResult, ...]
    total_trading_days: int
    total_successful_runs: int
    overall_pass_rate: Decimal
    generated_at: str


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 2 — Alpha Measurement
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class BenchmarkComparison:
    """Comparison of strategy performance against a benchmark index."""

    benchmark_code: str  # "NIFTY_50", "NIFTY_500"
    benchmark_name: str
    strategy_return: Decimal
    benchmark_return: Decimal
    alpha: Decimal  # strategy_return - benchmark_return
    excess_return: Decimal
    relative_performance: Decimal  # (strategy_return / benchmark_return) - 1
    annualized_return: Decimal
    benchmark_annualized_return: Decimal
    cagr: Decimal
    benchmark_cagr: Decimal
    rolling_returns: tuple[dict[str, Any], ...]  # date → strategy_return, benchmark_return


@dataclass(frozen=True, slots=True)
class AlphaAnalysisReport:
    """Complete alpha analysis for a strategy against multiple benchmarks."""

    strategy_name: str
    strategy_id: int
    period_label: str
    start_date: date
    end_date: date
    comparisons: tuple[BenchmarkComparison, ...]
    best_alpha: Decimal | None
    worst_alpha: Decimal | None
    avg_alpha: Decimal | None
    measurability: Measurability = _MEASURABLE


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 3 — Strategy Scorecards
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class StrategyScorecard:
    """Professional strategy scorecard with all performance metrics.

    Every metric is computed deterministically from historical screening
    results and market data. All metrics are reproducible.
    """

    strategy_name: str
    strategy_id: int
    period_label: str
    start_date: date | None
    end_date: date | None
    total_trading_days: int
    total_runs: int

    # Return-derived metrics. ``None`` means "not measurable" -- see
    # ``measurability`` for why. Never 0 as a stand-in for unmeasured.
    cagr: Decimal | None  # Compound Annual Growth Rate
    annual_return: Decimal | None
    cumulative_return: Decimal | None
    avg_holding_return: Decimal | None
    best_return: Decimal | None
    worst_return: Decimal | None

    # Win/loss metrics
    win_rate: Decimal | None  # fraction of positive-return periods
    avg_winner: Decimal | None  # average return of winning periods
    avg_loser: Decimal | None  # average return of losing periods
    total_wins: int | None
    total_losses: int | None
    profit_factor: Decimal | None  # sum(gains) / abs(sum(losses))

    # Risk metrics
    max_drawdown: Decimal | None  # largest peak-to-trough decline
    max_drawdown_duration: int | None  # days to recover from max drawdown
    volatility: Decimal | None  # annualized standard deviation of returns
    downside_volatility: Decimal | None  # annualized downside deviation

    # Risk-adjusted return metrics
    sharpe_ratio: Decimal | None  # risk-free rate assumed 0
    sortino_ratio: Decimal | None
    calmar_ratio: Decimal | None  # CAGR / max_drawdown
    information_ratio: Decimal | None  # excess return / tracking error

    # Market-relative metrics
    alpha: Decimal | None  # excess return over risk-free / benchmark
    beta: Decimal | None  # sensitivity to benchmark
    r_squared: Decimal | None  # goodness of fit to benchmark

    # Screening-specific metrics. These are derived from run *stats*, not from
    # returns, so they stay measurable even with no forward returns at all.
    avg_pass_rate: Decimal
    avg_top_rank_stability: Decimal
    avg_momentum_score: Decimal
    avg_buy_setup_score: Decimal
    false_positive_rate: Decimal | None  # passed but underperformed
    false_negative_rate: Decimal | None  # failed but outperformed

    measurability: Measurability = _MEASURABLE

    # Distribution
    monthly_returns: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    yearly_returns: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    rolling_sharpe: tuple[dict[str, Any], ...] = field(default_factory=tuple)


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 4 — Rule Effectiveness Analysis
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class RuleEffectiveness:
    """Detailed effectiveness analysis for a single rule."""

    rule_id: str
    engine_id: str
    rule_name: str
    total_evaluations: int

    # Pass/fail frequency
    pass_count: int
    fail_count: int
    pass_rate: Decimal

    # Contribution to outcomes. ``None`` when the rule was never evaluated on
    # that side of the outcome split -- an absent average, not an average of 0.
    contribution_to_successful: Decimal | None  # avg contribution when successful
    contribution_to_unsuccessful: Decimal | None  # avg contribution when unsuccessful
    # ``None`` when no matured forward return exists for the (run, security)
    # pairs this rule was evaluated on. Never a momentum score standing in for
    # a return -- that conflation was the 2026-08-09 audit's finding 1.2.4.
    avg_return_when_passes: Decimal | None  # average return when rule passes
    avg_return_when_fails: Decimal | None  # average return when rule fails

    # Statistical significance (simplified)
    return_delta: Decimal | None  # avg_return_when_passes - avg_return_when_fails
    significance_score: Decimal | None  # 0-1, higher = more statistically significant

    # Classification. All three are return-derived, so all three are ``None``
    # when returns are unavailable: an unmeasured rule is not a "weak" rule.
    is_weak: bool | None  # low pass_rate AND low return_delta
    is_redundant: bool | None  # pass_rate > 0.95 (rarely fails)
    is_high_value: bool | None  # high return_delta AND reasonable pass_rate


@dataclass(frozen=True, slots=True)
class RuleEffectivenessReport:
    """Complete rule effectiveness analysis for a strategy."""

    strategy_name: str
    strategy_id: int
    total_runs_analyzed: int
    date_range: tuple[date, date] | None
    rules: tuple[RuleEffectiveness, ...]
    weak_rules: tuple[RuleEffectiveness, ...]
    redundant_rules: tuple[RuleEffectiveness, ...]
    high_value_rules: tuple[RuleEffectiveness, ...]
    summary: str
    measurability: Measurability = _MEASURABLE


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 5 — Engine Effectiveness
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class EngineEffectiveness:
    """Effectiveness analysis for a single engine."""

    engine_id: str
    engine_name: str
    total_evaluations: int
    avg_score: Decimal
    avg_rules_passed: Decimal
    avg_rules_failed: Decimal
    avg_pass_rate: Decimal
    contribution_to_final_score: Decimal  # avg contribution to final momentum score
    # Return-derived; ``None`` when no matured forward returns exist.
    correlation_with_outcome: Decimal | None  # correlation of engine score with outcome
    improves_performance: bool | None  # does enabling this engine improve results?
    avg_forward_return_when_engine_scores_high: Decimal | None


@dataclass(frozen=True, slots=True)
class EngineEffectivenessReport:
    """Complete engine effectiveness analysis."""

    strategy_name: str
    strategy_id: int
    total_runs_analyzed: int
    engines: tuple[EngineEffectiveness, ...]
    best_engine: str  # engine_id with the highest measured forward return
    worst_engine: str  # engine_id with the lowest measured forward return
    recommended_exclusions: tuple[str, ...]  # engines that don't improve performance
    summary: str
    measurability: Measurability = _MEASURABLE


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 6 — Parameter Research
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class ParameterExperimentResult:
    """Result of a single parameter experiment variant."""

    variant_name: str
    overrides: tuple[dict[str, Any], ...]
    run_count: int
    avg_momentum_score: Decimal
    avg_buy_setup_score: Decimal
    avg_pass_rate: Decimal
    scorecard: StrategyScorecard | None = None


@dataclass(frozen=True, slots=True)
class ParameterExperimentReport:
    """Complete parameter experiment report."""

    experiment_name: str
    base_strategy_name: str
    base_result: ParameterExperimentResult
    variants: tuple[ParameterExperimentResult, ...]
    best_variant: str | None
    best_improvement: Decimal
    parameter_sensitivity: dict[str, Any]  # which parameters had the most impact
    summary: str


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 7 — Historical Replay (extended)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class ReplayIndicators:
    """Complete indicator state as of a historical date."""

    sma20: Decimal | None
    sma50: Decimal | None
    sma200: Decimal | None
    ema20: Decimal | None
    ema50: Decimal | None
    rsi14: Decimal | None
    atr14: Decimal | None
    adx14: Decimal | None
    volume_sma20: Decimal | None
    volume_ratio: Decimal | None
    close: Decimal
    high_52w: Decimal | None
    low_52w: Decimal | None
    percent_from_52w_high: Decimal | None
    percent_from_52w_low: Decimal | None
    additional: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ReplayRuleEvaluation:
    """A single rule evaluation as it existed on a historical date."""

    rule_id: str
    engine_id: str
    passed: bool
    raw_value: Decimal | None
    threshold: Decimal | None
    operator: str
    weight: Decimal
    contribution: Decimal
    explanation: str


@dataclass(frozen=True, slots=True)
class ReplayEngineScore:
    """A single engine score as it existed on a historical date."""

    engine_id: str
    score: Decimal
    passed_gate: bool
    weight: Decimal
    rules: tuple[ReplayRuleEvaluation, ...]


@dataclass(frozen=True, slots=True)
class ReplaySecurityResult:
    """Complete replay result for one security on a historical date."""

    security_id: int
    symbol: str
    rank: int | None
    momentum_score: Decimal
    buy_setup_score: Decimal
    hard_filters_passed: bool
    indicators: ReplayIndicators
    engines: tuple[ReplayEngineScore, ...]


@dataclass(frozen=True, slots=True)
class HistoricalReplayResult:
    """Complete replay of the screening engine for a historical date."""

    run_id: int
    strategy_name: str
    run_date: date
    total_evaluated: int
    total_passed: int
    total_failed: int
    securities: tuple[ReplaySecurityResult, ...]
    config_hash: str
    data_version: str


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 8 — Research Dashboard (aggregation models)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class DashboardSummary:
    """Aggregated research dashboard data."""

    strategy_name: str
    strategy_id: int
    scorecard: StrategyScorecard | None
    alpha_analysis: AlphaAnalysisReport | None
    rule_effectiveness: RuleEffectivenessReport | None
    engine_effectiveness: EngineEffectivenessReport | None
    historical_validation: HistoricalValidationReport | None
    ranking_stability: Decimal
    false_positive_rate: Decimal
    false_negative_rate: Decimal
    top_experiments: tuple[ParameterExperimentReport, ...]