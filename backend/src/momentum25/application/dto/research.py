"""Research & Validation Platform DTOs — stable API contracts.

These Pydantic models are the boundary between the application and transport layers
for all research capabilities: historical screening, validation, evaluation,
contribution analysis, strategy comparison, and experiments.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


# ── Historical Screening ──────────────────────────────────────────────────


class HistoricalScreeningRequest(BaseModel):
    """Request to execute a historical screening run."""

    strategy_name: str = "minervini_trend_template"
    as_of_date: date
    symbol_filter: list[str] | None = None


class HistoricalScreeningResponse(BaseModel):
    """Response from a historical screening run."""

    run_id: int
    run_date: date
    total_evaluated: int
    total_passed: int
    total_failed: int
    strategy_name: str


# ── Validation / Run Comparison ──────────────────────────────────────────


class RankingComparisonDTO(BaseModel):
    """A single ranking difference between two runs."""

    security_id: int
    symbol: str
    rank_a: int | None = None
    rank_b: int | None = None
    rank_delta: int | None = None
    direction: str | None = None  # "up", "down", "unchanged", "new", "dropped"


class ScoreComparisonDTO(BaseModel):
    """A single score difference between two runs."""

    security_id: int
    symbol: str
    momentum_a: Decimal | None = None
    momentum_b: Decimal | None = None
    momentum_delta: Decimal | None = None
    buy_setup_a: Decimal | None = None
    buy_setup_b: Decimal | None = None
    buy_setup_delta: Decimal | None = None


class RuleComparisonDTO(BaseModel):
    """A single rule difference between two runs for a security."""

    security_id: int
    symbol: str
    rule_id: str
    engine_id: str
    passed_a: bool
    passed_b: bool
    changed: bool


class RunComparisonResponse(BaseModel):
    """Complete comparison report between two runs."""

    run_id_a: int
    run_id_b: int
    run_date_a: date
    run_date_b: date
    strategy_name: str
    ranking_changed: bool
    score_changed: bool
    ranking_diffs: list[RankingComparisonDTO]
    score_diffs: list[ScoreComparisonDTO]
    rule_diffs: list[RuleComparisonDTO]
    top_gainers: list[RankingComparisonDTO]
    top_losers: list[RankingComparisonDTO]
    is_identical: bool

    # ── Comparability disclosure (Phase 0.3/0.4) ────────────────────────────
    # Indicator formulas are not covered by config_hash, so two runs can share a
    # strategy yet be computed with different RSI/ATR definitions. Correcting
    # those formulas shifts RSI by a mean of 6.7 points and ATR by ~3.8%, which
    # would otherwise be silently attributed to whatever change was under
    # investigation. These fields disclose the mismatch instead of blocking the
    # comparison -- comparing across versions is legitimate, doing it unknowingly
    # is not.
    indicator_version_a: int | None = None
    indicator_version_b: int | None = None
    indicator_versions_differ: bool = False


class DeterminismVerificationResponse(BaseModel):
    """Result of a determinism verification test."""

    run_id_a: int
    run_id_b: int
    is_deterministic: bool
    ranking_changed: bool
    score_changed: bool
    rule_diffs: int


# ── Strategy Evaluation ──────────────────────────────────────────────────


class HistoricalRunSummaryDTO(BaseModel):
    """Summary of a single historical screening run."""

    run_id: int
    strategy_name: str
    run_date: date
    total_evaluated: int
    total_passed: int
    total_failed: int
    data_version: str
    config_hash: str
    started_at: datetime | None = None
    finished_at: datetime | None = None


class PortfolioPerformanceDTO(BaseModel):
    """Performance metrics for a strategy across historical runs."""

    strategy_name: str
    run_count: int
    first_run_date: date | None = None
    last_run_date: date | None = None

    # Score statistics
    avg_momentum_score: Decimal = Decimal("0")
    median_momentum_score: Decimal = Decimal("0")
    avg_buy_setup_score: Decimal = Decimal("0")
    median_buy_setup_score: Decimal = Decimal("0")
    momentum_score_volatility: Decimal = Decimal("0")
    buy_setup_score_volatility: Decimal = Decimal("0")
    max_momentum_score: Decimal = Decimal("0")
    min_momentum_score: Decimal = Decimal("0")

    # Risk metrics
    max_drawdown_pct: Decimal = Decimal("0")
    avg_pass_rate: Decimal = Decimal("0")
    avg_top_rank_stability: Decimal = Decimal("0")
    sharpe_ratio: Decimal = Decimal("0")
    sortino_ratio: Decimal = Decimal("0")
    profit_factor: Decimal = Decimal("0")


class ScorePointDTO(BaseModel):
    """A single score point in a history."""

    run_date: date
    security_id: int
    rank: int
    momentum_score: Decimal
    buy_setup_score: Decimal


class StrategyEvaluationResponse(BaseModel):
    """Complete strategy evaluation result."""

    strategy_name: str
    performance: PortfolioPerformanceDTO
    run_summaries: list[HistoricalRunSummaryDTO]
    score_history: list[ScorePointDTO]


# ── Contribution Analysis ────────────────────────────────────────────────


class RuleContributionStatsDTO(BaseModel):
    """Statistics for a single rule across multiple runs."""

    rule_id: str
    engine_id: str
    pass_count: int
    fail_count: int
    avg_contribution: Decimal
    total_contribution: Decimal
    importance_score: Decimal
    pass_rate: Decimal
    is_redundant: bool = False


class EngineContributionStatsDTO(BaseModel):
    """Aggregated statistics for an engine across multiple runs."""

    engine_name: str
    rule_count: int
    avg_pass_rate: Decimal
    avg_importance: Decimal
    total_importance: Decimal


class ContributionAnalysisResponse(BaseModel):
    """Complete contribution analysis report."""

    strategy_name: str
    run_count: int
    date_range: str | None = None
    engine_stats: list[EngineContributionStatsDTO]
    top_rules: list[RuleContributionStatsDTO]
    bottom_rules: list[RuleContributionStatsDTO]
    redundant_rules: list[RuleContributionStatsDTO]


# ── Strategy Comparison ──────────────────────────────────────────────────


class StrategyComparisonPointDTO(BaseModel):
    """A single security comparison between two strategies."""

    security_id: int
    symbol: str
    rank_a: int | None = None
    rank_b: int | None = None
    momentum_a: Decimal | None = None
    momentum_b: Decimal | None = None
    buy_setup_a: Decimal | None = None
    buy_setup_b: Decimal | None = None
    agreement: bool = False  # both passed or both failed


class StrategyComparisonResponse(BaseModel):
    """Complete strategy comparison report."""

    strategy_a_name: str
    strategy_b_name: str
    total_comparisons: int
    agreement_count: int
    agreement_rate: Decimal
    a_wins: int
    b_wins: int
    comparisons: list[StrategyComparisonPointDTO]
    rule_level_diffs: list[dict[str, Any]]


# ── Experiment Framework ─────────────────────────────────────────────────


class ParameterOverrideDTO(BaseModel):
    """A single parameter override for an experiment."""

    parameter_path: str = Field(description="Dot-separated path, e.g. 'engines.trend_template.weight'")
    value: str = Field(description="Stringified value to set")


class ExperimentConfigDTO(BaseModel):
    """Configuration for an experiment run."""

    base_strategy_name: str
    overrides: list[ParameterOverrideDTO]
    run_dates: list[date] | None = None
    symbol_filter: list[str] | None = None


class ExperimentResultDTO(BaseModel):
    """Result of a single experiment variant."""

    variant_label: str
    run_id: int
    run_date: date
    total_evaluated: int
    total_passed: int
    avg_momentum_score: Decimal
    avg_buy_setup_score: Decimal


class ExperimentResponse(BaseModel):
    """Complete experiment report."""

    base_strategy_name: str
    variant_label: str
    run_count: int
    date_range: str | None = None
    base_results: list[ExperimentResultDTO]
    variant_results: list[ExperimentResultDTO]
    avg_improvement: Decimal = Decimal("0")
    best_run_date: date | None = None
    is_better: bool = False
    summary: str = ""