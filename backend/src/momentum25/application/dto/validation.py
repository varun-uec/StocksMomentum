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


class MeasurabilityDTO(BaseModel):
    """Whether return-derived metrics on this response could be computed at all.

    ``forward_returns_available: false`` means every ``null`` metric below is
    *unmeasured*, not *measured as zero*. ``reason`` is a stable identifier
    (``"no_forward_returns"``, ``"no_runs"``) the UI keys its copy off.
    """

    forward_returns_available: bool
    reason: str | None = None


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
    best_alpha: Decimal | None = None
    worst_alpha: Decimal | None = None
    avg_alpha: Decimal | None = None
    measurability: MeasurabilityDTO


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

    # Return-derived metrics. ``None`` = not measurable; see ``measurability``.
    # Never 0 as a stand-in for unmeasured (2026-08-09 audit §1.2.3).
    cagr: Decimal | None = None
    annual_return: Decimal | None = None
    cumulative_return: Decimal | None = None
    avg_holding_return: Decimal | None = None
    best_return: Decimal | None = None
    worst_return: Decimal | None = None

    # Win/loss metrics
    win_rate: Decimal | None = None
    avg_winner: Decimal | None = None
    avg_loser: Decimal | None = None
    total_wins: int | None = None
    total_losses: int | None = None
    profit_factor: Decimal | None = None

    # Risk metrics
    max_drawdown: Decimal | None = None
    max_drawdown_duration: int | None = None
    volatility: Decimal | None = None
    downside_volatility: Decimal | None = None

    # Risk-adjusted return metrics
    sharpe_ratio: Decimal | None = None
    sortino_ratio: Decimal | None = None
    calmar_ratio: Decimal | None = None
    information_ratio: Decimal | None = None

    # Market-relative metrics
    alpha: Decimal | None = None
    beta: Decimal | None = None
    r_squared: Decimal | None = None

    # Screening-specific metrics (derived from run stats, always measurable)
    avg_pass_rate: Decimal = Decimal("0")
    avg_momentum_score: Decimal = Decimal("0")
    avg_buy_setup_score: Decimal = Decimal("0")
    false_positive_rate: Decimal | None = None
    false_negative_rate: Decimal | None = None

    measurability: MeasurabilityDTO

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
    contribution_to_successful: Decimal | None = None
    contribution_to_unsuccessful: Decimal | None = None
    avg_return_when_passes: Decimal | None = None
    avg_return_when_fails: Decimal | None = None
    return_delta: Decimal | None = None
    significance_score: Decimal | None = None
    is_weak: bool | None = None
    is_redundant: bool | None = None
    is_high_value: bool | None = None


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
    measurability: MeasurabilityDTO


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
    correlation_with_outcome: Decimal | None = None
    improves_performance: bool | None = None
    # Replaces ``standalone_performance``, which reported the run's average
    # momentum *score* as if it were a return (2026-08-09 audit §1.2.4/§2.3).
    avg_forward_return_when_engine_scores_high: Decimal | None = None


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