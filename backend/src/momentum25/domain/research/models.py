"""Value objects for the Research & Validation Platform.

All types are immutable, deterministic, and carry no I/O dependencies.
They are the bedrock of Phase 4's historical analysis, validation,
evaluation, comparison, and experimentation capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any


# ═══════════════════════════════════════════════════════════════════════════════
# Historical Screening
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class HistoricalSnapshot:
    """An immutable snapshot of one security in one screening run.

    Contains all data needed for reproducibility: indicators, rule results,
    engine scores, final scores, and ranking. Maps directly to the persisted
    ``screening_results`` + ``rule_results`` + ``universe_membership`` tables.
    """

    run_id: int
    strategy_id: int
    run_date: date
    security_id: int
    symbol: str
    rank: int | None
    momentum_score: Decimal
    buy_setup_score: Decimal
    hard_filters_passed: bool
    engine_results: dict[str, Any]  # engine_id → {score, passed_gate, rules: [...]}
    rule_results: tuple[dict[str, Any], ...]  # each with rule_id, passed, raw_value, etc.


@dataclass(frozen=True, slots=True)
class HistoricalRunSummary:
    """Aggregated summary of one historical screening run."""

    run_id: int
    strategy_id: int
    strategy_name: str
    run_date: date
    data_version: str
    config_hash: str
    total_evaluated: int
    total_passed: int
    total_failed: int
    started_at: Any
    finished_at: Any
    stats: dict[str, Any]


@dataclass(frozen=True, slots=True)
class HistoricalScreeningRequest:
    """Request to execute a screening for a historical trading date."""

    strategy_name: str
    as_of_date: date
    symbol_filter: list[str] | None = None


# ═══════════════════════════════════════════════════════════════════════════════
# Validation Framework
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class RankingComparison:
    """Diff of rankings between two runs for the same security."""

    security_id: int
    symbol: str
    run_a_rank: int | None
    run_b_rank: int | None
    rank_delta: int | None  # positive = improved in B, negative = regressed
    run_a_score: Decimal
    run_b_score: Decimal
    score_delta: Decimal


@dataclass(frozen=True, slots=True)
class ScoreComparison:
    """Score-level comparison between two runs."""

    security_id: int
    symbol: str
    momentum_score_a: Decimal
    momentum_score_b: Decimal
    momentum_delta: Decimal
    buy_setup_a: Decimal
    buy_setup_b: Decimal
    buy_setup_delta: Decimal


@dataclass(frozen=True, slots=True)
class RuleComparison:
    """Rule-level comparison between two runs for one security."""

    security_id: int
    symbol: str
    rule_id: str
    engine_id: str
    passed_a: bool
    passed_b: bool
    raw_value_a: Decimal | None
    raw_value_b: Decimal | None


@dataclass(frozen=True, slots=True)
class RunComparisonReport:
    """Deterministic comparison of two historical runs."""

    run_id_a: int
    run_id_b: int
    run_date_a: date
    run_date_b: date
    strategy_name: str

    # Aggregated stats
    common_securities: int
    ranking_changed: int
    ranking_unchanged: int
    ranking_regressed: int
    ranking_improved: int
    score_changed: int
    score_unchanged: int

    rank_deltas: tuple[RankingComparison, ...]
    score_deltas: tuple[ScoreComparison, ...]
    rule_diffs: tuple[RuleComparison, ...]

    # Top movers and shakers for reporting
    top_gainers: tuple[RankingComparison, ...] = field(default_factory=tuple)  # biggest rank improvement
    top_losers: tuple[RankingComparison, ...] = field(default_factory=tuple)   # biggest rank regression

    def is_identical(self) -> bool:
        """Return True if no ranking or score differences were detected."""
        return self.ranking_changed == 0 and self.score_changed == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Performance / Evaluation Metrics (Priority 4)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class PortfolioPerformance:
    """Performance metrics for a set of historical screening runs.

    All metrics are computed deterministically from ranking/score history.
    No market data required — metrics are relative to screening rank stability
    and score trajectories.
    """

    strategy_id: int
    strategy_name: str
    run_count: int
    first_run_date: date | None
    last_run_date: date | None

    # Score-based metrics
    avg_momentum_score: Decimal
    median_momentum_score: Decimal
    avg_buy_setup_score: Decimal
    median_buy_setup_score: Decimal
    momentum_score_volatility: Decimal
    buy_setup_score_volatility: Decimal
    max_momentum_score: Decimal
    min_momentum_score: Decimal
    max_drawdown_pct: Decimal  # largest peak-to-trough decline in scores

    # Rank-based metrics
    avg_pass_rate: Decimal  # fraction of securities passing hard filters
    avg_top_rank_stability: Decimal  # fraction of top-10 that stayed in top-10

    # Risk-like metrics from score time series
    sharpe_ratio: Decimal  # (mean_score - 0) / std_score, annualised
    sortino_ratio: Decimal  # (mean_score - 0) / downside_std
    profit_factor: Decimal  # sum(gain_days) / abs(sum(loss_days))


@dataclass(frozen=True, slots=True)
class StrategyEvaluationResult:
    """Complete evaluation result for one strategy over a historical period."""

    strategy_name: str
    strategy_id: int
    performance: PortfolioPerformance
    run_summaries: tuple[HistoricalRunSummary, ...]
    score_history: tuple[dict[str, Any], ...]  # per-security score trajectories


# ═══════════════════════════════════════════════════════════════════════════════
# Rule & Engine Contribution Analysis (Priority 5)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class RuleContributionStats:
    """Cross-run statistics for a single rule."""

    rule_id: str
    engine_id: str
    run_count: int
    pass_count: int
    fail_count: int
    pass_rate: Decimal  # pass_count / run_count
    avg_contribution: Decimal
    total_contribution: Decimal
    avg_raw_value: Decimal | None
    importance_score: Decimal  # contribution × pass_rate (higher = more impactful)


@dataclass(frozen=True, slots=True)
class EngineContributionStats:
    """Cross-run statistics for a single engine."""

    engine_id: str
    rule_stats: tuple[RuleContributionStats, ...]
    run_count: int
    avg_engine_score: Decimal
    avg_rules_passed: Decimal
    avg_rules_failed: Decimal
    importance_weight: Decimal

    @property
    def avg_pass_rate(self) -> Decimal:
        """Weighted average of rule pass rates within this engine."""
        if not self.rule_stats:
            return Decimal("0")
        return sum((rs.pass_rate for rs in self.rule_stats), Decimal("0")) / len(self.rule_stats)


@dataclass(frozen=True, slots=True)
class ContributionAnalysisReport:
    """Complete rule/engine contribution analysis across runs."""

    strategy_name: str
    strategy_id: int
    run_count: int
    date_range: tuple[date, date] | None
    engine_stats: tuple[EngineContributionStats, ...]
    top_rules: tuple[RuleContributionStats, ...]  # top 10 rules by importance
    bottom_rules: tuple[RuleContributionStats, ...]  # bottom 10 rules by importance
    redundant_rules: tuple[RuleContributionStats, ...]  # rules that never/rarely fail


# ═══════════════════════════════════════════════════════════════════════════════
# Strategy Comparison (Priority 6)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class StrategyComparisonPoint:
    """Comparison of two strategies on the same run date."""

    run_date: date
    strategy_a_score: Decimal
    strategy_b_score: Decimal
    score_delta: Decimal
    strategy_a_rank: int | None
    strategy_b_rank: int | None
    rank_delta: int | None
    strategy_a_passed: bool
    strategy_b_passed: bool


@dataclass(frozen=True, slots=True)
class StrategyComparisonReport:
    """Deterministic comparison of two strategy configurations."""

    strategy_a_name: str
    strategy_b_name: str
    strategy_a_id: int
    strategy_b_id: int
    common_run_dates: int

    # Aggregate comparison
    avg_score_delta: Decimal
    median_score_delta: Decimal
    max_score_delta: Decimal
    rank_correlation: Decimal  # Spearman-like rank correlation (simplified)

    score_deltas: tuple[StrategyComparisonPoint, ...]
    rule_differences: tuple[RuleComparison, ...]

    # Which strategy wins by various measures
    strategy_a_wins_score: int  # count of dates where A scored higher
    strategy_b_wins_score: int
    strategy_a_wins_pass_rate: int
    strategy_b_wins_pass_rate: int


# ═══════════════════════════════════════════════════════════════════════════════
# Experiment Framework (Priority 7)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass(frozen=True, slots=True)
class ParameterOverride:
    """A single parameter modification for an experiment."""

    parameter_path: str  # e.g. "weight", "params.norm_min", "threshold"
    engine_id: str | None = None  # None = top-level strategy parameter
    rule_id: str | None = None
    old_value: Any = None
    new_value: Any = None


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    """Configuration for a controlled screening experiment."""

    name: str
    description: str
    base_strategy_name: str
    base_strategy_id: int
    overrides: tuple[ParameterOverride, ...]
    run_dates: tuple[date, ...]  # dates to test on


@dataclass(frozen=True, slots=True)
class ExperimentResult:
    """Result of a single experiment variant."""

    experiment_name: str
    variant_name: str
    overrides: tuple[ParameterOverride, ...]
    config_hash: str
    run_id: int
    run_date: date
    total_evaluated: int
    total_passed: int
    avg_momentum_score: Decimal
    avg_buy_setup_score: Decimal
    performance: PortfolioPerformance | None = None


@dataclass(frozen=True, slots=True)
class ExperimentReport:
    """Complete experiment report comparing base vs variants."""

    experiment_name: str
    description: str
    base_strategy_name: str
    variants: tuple[ExperimentResult, ...]
    base_results: tuple[ExperimentResult, ...]

    # Comparison summary
    best_variant: str | None  # name of variant with highest avg momentum score
    best_variant_improvement: Decimal  # improvement over base
    summary: str