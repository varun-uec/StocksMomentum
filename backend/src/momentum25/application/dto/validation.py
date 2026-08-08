"""DTOs for Strategy Validation & Alpha Research (Phase 6).

These Pydantic models are the stable API contracts for historical validation,
alpha measurement, scorecards, rule/engine effectiveness, and parameter research.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 1 — Historical Validation
# ═══════════════════════════════════════════════════════════════════════════════


class ValidationWindowDTO(BaseModel):
    """A configurable validation window."""

    label: str
    start_date: date
    end_date: date
    trading_days: int


class HistoricalValidationResultDTO(BaseModel):
    """Results for a single validation window."""

    strategy_name: str
    window: ValidationWindowDTO
    total_runs: int
    successful_runs: int
    failed_runs: int
    run_ids: list[int]
    summary: dict[str, Any]


class HistoricalValidationResponse(BaseModel):
    """Complete historical validation report."""

    strategy_name: str
    strategy_id: int
    windows: list[HistoricalValidationResultDTO]
    total_trading_days: int
    total_successful_runs: int
    overall_pass_rate: Decimal
    generated_at: str


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 2 — Alpha Measurement
# ═══════════════════════════════════════════════════════════════════════════════


class BenchmarkComparisonDTO(BaseModel):
    """Comparison against a single benchmark."""

    benchmark_code: str
    benchmark_name: str
    strategy_return: Decimal
    benchmark_return: Decimal
    alpha: Decimal
    excess_return: Decimal
    relative_performance: Decimal
    annualized_return: Decimal
    benchmark_annualized_return: Decimal
    cagr: Decimal
    benchmark_cagr: Decimal
    rolling_returns: list[dict[str, Any]]


class AlphaAnalysisResponse(BaseModel):
    """Complete alpha analysis report."""

    strategy_name: str
    strategy_id: int
    period_label: str
    start_date: date
    end_date: date
    comparisons: list[BenchmarkComparisonDTO]
    best_alpha: Decimal
    worst_alpha: Decimal
    avg_alpha: Decimal


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 3 — Strategy Scorecards
# ═══════════════════════════════════════════════════════════════════════════════


class StrategyScorecardDTO(BaseModel):
    """Professional strategy scorecard with all performance metrics."""

    strategy_name: str
    strategy_id: int
    period_label: str
    start_date: date | None = None
    end_date: date | None = None
    total_trading_days: int
    total_runs: int

    # Return metrics
    cagr: Decimal = Decimal("0")
    annual_return: Decimal = Decimal("0")
    cumulative_return: Decimal = Decimal("0")
    avg_holding_return: Decimal = Decimal("0")
    best_return: Decimal = Decimal("0")
    worst_return: Decimal = Decimal("0")

    # Win/loss metrics
    win_rate: Decimal = Decimal("0")
    avg_winner: Decimal = Decimal("0")
    avg_loser: Decimal = Decimal("0")
    total_wins: int = 0
    total_losses: int = 0
    profit_factor: Decimal = Decimal("0")

    # Risk metrics
    max_drawdown: Decimal = Decimal("0")
    max_drawdown_duration: int = 0
    volatility: Decimal = Decimal("0")
    downside_volatility: Decimal = Decimal("0")

    # Risk-adjusted return metrics
    sharpe_ratio: Decimal = Decimal("0")
    sortino_ratio: Decimal = Decimal("0")
    calmar_ratio: Decimal = Decimal("0")
    information_ratio: Decimal = Decimal("0")

    # Market-relative metrics
    alpha: Decimal = Decimal("0")
    beta: Decimal = Decimal("0")
    r_squared: Decimal = Decimal("0")

    # Screening-specific metrics
    avg_pass_rate: Decimal = Decimal("0")
    avg_momentum_score: Decimal = Decimal("0")
    avg_buy_setup_score: Decimal = Decimal("0")
    false_positive_rate: Decimal = Decimal("0")
    false_negative_rate: Decimal = Decimal("0")

    # Distribution
    monthly_returns: list[dict[str, Any]] = Field(default_factory=list)
    yearly_returns: list[dict[str, Any]] = Field(default_factory=list)
    rolling_sharpe: list[dict[str, Any]] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 4 — Rule Effectiveness
# ═══════════════════════════════════════════════════════════════════════════════


class RuleEffectivenessDTO(BaseModel):
    """Effectiveness analysis for a single rule."""

    rule_id: str
    engine_id: str
    rule_name: str
    total_evaluations: int
    pass_count: int
    fail_count: int
    pass_rate: Decimal
    contribution_to_successful: Decimal
    contribution_to_unsuccessful: Decimal
    avg_return_when_passes: Decimal
    avg_return_when_fails: Decimal
    return_delta: Decimal
    significance_score: Decimal
    is_weak: bool = False
    is_redundant: bool = False
    is_high_value: bool = False


class RuleEffectivenessResponse(BaseModel):
    """Complete rule effectiveness analysis report."""

    strategy_name: str
    strategy_id: int
    total_runs_analyzed: int
    date_range: str | None = None
    rules: list[RuleEffectivenessDTO]
    weak_rules: list[RuleEffectivenessDTO]
    redundant_rules: list[RuleEffectivenessDTO]
    high_value_rules: list[RuleEffectivenessDTO]
    summary: str


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 5 — Engine Effectiveness
# ═══════════════════════════════════════════════════════════════════════════════


class EngineEffectivenessDTO(BaseModel):
    """Effectiveness analysis for a single engine."""

    engine_id: str
    engine_name: str
    total_evaluations: int
    avg_score: Decimal
    avg_rules_passed: Decimal
    avg_rules_failed: Decimal
    avg_pass_rate: Decimal
    contribution_to_final_score: Decimal
    correlation_with_outcome: Decimal
    improves_performance: bool = False
    standalone_performance: Decimal


class EngineEffectivenessResponse(BaseModel):
    """Complete engine effectiveness analysis report."""

    strategy_name: str
    strategy_id: int
    total_runs_analyzed: int
    engines: list[EngineEffectivenessDTO]
    best_engine: str
    worst_engine: str
    recommended_exclusions: list[str]
    summary: str


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 6 — Parameter Research
# ═══════════════════════════════════════════════════════════════════════════════


class ParameterOverrideDTO(BaseModel):
    """A single parameter override for an experiment."""

    parameter_path: str = Field(description="Dot-separated path")
    engine_id: str | None = None
    rule_id: str | None = None
    old_value: str | None = None
    new_value: str = Field(description="New value to set")


class ParameterExperimentVariantDTO(BaseModel):
    """Configuration for an experiment variant."""

    name: str = Field(description="Variant name")
    overrides: list[ParameterOverrideDTO]


class ParameterExperimentRequest(BaseModel):
    """Request to run a parameter experiment."""

    experiment_name: str
    base_strategy_name: str = "minervini_trend_template"
    variants: list[ParameterExperimentVariantDTO]
    run_dates: list[date] | None = None


class ParameterExperimentResultDTO(BaseModel):
    """Result of a single experiment variant."""

    variant_name: str
    run_count: int
    avg_momentum_score: Decimal
    avg_buy_setup_score: Decimal
    avg_pass_rate: Decimal


class ParameterExperimentResponse(BaseModel):
    """Complete parameter experiment report."""

    experiment_name: str
    base_strategy_name: str
    base_result: ParameterExperimentResultDTO
    variants: list[ParameterExperimentResultDTO]
    best_variant: str | None = None
    best_improvement: Decimal = Decimal("0")
    parameter_sensitivity: dict[str, Any] = Field(default_factory=dict)
    summary: str


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 7 — Historical Replay (extended)
# ═══════════════════════════════════════════════════════════════════════════════


class ReplayIndicatorDTO(BaseModel):
    """Indicators as of a historical date."""

    sma20: Decimal | None = None
    sma50: Decimal | None = None
    sma200: Decimal | None = None
    ema20: Decimal | None = None
    ema50: Decimal | None = None
    rsi14: Decimal | None = None
    atr14: Decimal | None = None
    adx14: Decimal | None = None
    volume_sma20: Decimal | None = None
    volume_ratio: Decimal | None = None
    close: Decimal = Decimal("0")
    high_52w: Decimal | None = None
    low_52w: Decimal | None = None
    percent_from_52w_high: Decimal | None = None
    percent_from_52w_low: Decimal | None = None


class ReplayRuleEvaluationDTO(BaseModel):
    """Rule evaluation as of a historical date."""

    rule_id: str
    engine_id: str
    passed: bool
    raw_value: Decimal | None = None
    threshold: Decimal | None = None
    operator: str
    weight: Decimal
    contribution: Decimal
    explanation: str


class ReplayEngineScoreDTO(BaseModel):
    """Engine score as of a historical date."""

    engine_id: str
    score: Decimal
    passed_gate: bool
    weight: Decimal
    rules: list[ReplayRuleEvaluationDTO]


class ReplaySecurityResultDTO(BaseModel):
    """Complete replay result for one security."""

    security_id: int
    symbol: str
    rank: int | None = None
    momentum_score: Decimal
    buy_setup_score: Decimal
    hard_filters_passed: bool
    indicators: ReplayIndicatorDTO
    engines: list[ReplayEngineScoreDTO]


class HistoricalReplayDetailResponse(BaseModel):
    """Complete historical replay with full details."""

    run_id: int
    strategy_name: str
    run_date: date
    total_evaluated: int
    total_passed: int
    total_failed: int
    securities: list[ReplaySecurityResultDTO]
    config_hash: str
    data_version: str


# ═══════════════════════════════════════════════════════════════════════════════
# Priority 8 — Research Dashboard
# ═══════════════════════════════════════════════════════════════════════════════


class ResearchDashboardRequest(BaseModel):
    """Request for research dashboard data."""

    strategy_name: str = "minervini_trend_template"
    window_years: int = Field(default=1, ge=1, le=10)


class ResearchDashboardResponse(BaseModel):
    """Aggregated research dashboard data."""

    strategy_name: str
    strategy_id: int
    scorecard: StrategyScorecardDTO | None = None
    alpha_analysis: AlphaAnalysisResponse | None = None
    rule_effectiveness: RuleEffectivenessResponse | None = None
    engine_effectiveness: EngineEffectivenessResponse | None = None
    historical_validation: HistoricalValidationResponse | None = None
    ranking_stability: Decimal = Decimal("0")
    false_positive_rate: Decimal = Decimal("0")
    false_negative_rate: Decimal = Decimal("0")