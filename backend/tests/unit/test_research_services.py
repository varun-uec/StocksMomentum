"""Unit tests for the Research & Validation Platform domain services.

Tests cover all 7 priorities: historical screening domain models,
validation framework, strategy evaluation, contribution analysis,
strategy comparison, and experiment framework.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from momentum25.domain.research.models import (
    ContributionAnalysisReport,
    EngineContributionStats,
    ExperimentConfig,
    ExperimentReport,
    ExperimentResult,
    HistoricalRunSummary,
    HistoricalSnapshot,
    ParameterOverride,
    PortfolioPerformance,
    RankingComparison,
    RuleComparison,
    RuleContributionStats,
    RunComparisonReport,
    ScoreComparison,
    StrategyComparisonPoint,
    StrategyComparisonReport,
    StrategyEvaluationResult,
)
from momentum25.domain.research.services import (
    _compute_max_drawdown,
    _compute_profit_factor,
    _compute_sharpe,
    _compute_sortino,
    _safe_div,
    _variance,
    analyze_contribution,
    apply_parameter_overrides,
    compare_runs,
    compare_strategies,
    compute_performance,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for helpers and utility functions
# ═══════════════════════════════════════════════════════════════════════════════

class TestHelperFunctions:
    """Test internal helper functions used by domain services."""

    def test_safe_div_normal(self) -> None:
        """_safe_div returns quotient for valid division."""
        result = _safe_div(Decimal("10"), Decimal("2"))
        assert result == Decimal("5")

    def test_safe_div_zero_denominator(self) -> None:
        """_safe_div returns 0 when denominator is 0."""
        result = _safe_div(Decimal("10"), Decimal("0"))
        assert result == Decimal("0")

    def test_variance_empty(self) -> None:
        """_variance returns 0 for empty list."""
        result = _variance([], Decimal("0"))
        assert result == 0.0

    def test_variance_single(self) -> None:
        """_variance returns 0 for single value."""
        result = _variance([Decimal("5")], Decimal("5"))
        assert result == 0.0

    def test_variance_known_values(self) -> None:
        """_variance computes correctly for known values."""
        result = _variance(
            [Decimal("2"), Decimal("4"), Decimal("4"), Decimal("4"), Decimal("5"), Decimal("5"), Decimal("7"), Decimal("9")],
            Decimal("5"),
        )
        assert abs(result - 4.0) < 0.01

    def test_compute_max_drawdown_empty(self) -> None:
        """_compute_max_drawdown returns 0 for empty list."""
        assert _compute_max_drawdown([]) == Decimal("0")

    def test_compute_max_drawdown_no_drawdown(self) -> None:
        """_compute_max_drawdown returns 0 for monotonically increasing series."""
        scores = [Decimal("10"), Decimal("20"), Decimal("30"), Decimal("40")]
        assert _compute_max_drawdown(scores) == Decimal("0")

    def test_compute_max_drawdown_with_drawdown(self) -> None:
        """_compute_max_drawdown computes correctly."""
        scores = [Decimal("100"), Decimal("90"), Decimal("80"), Decimal("95"), Decimal("70")]
        # Peak = 100, trough = 70, dd = (100-70)/100 = 0.3
        result = _compute_max_drawdown(scores)
        assert result == Decimal("0.3")

    def test_compute_sharpe_empty(self) -> None:
        """_compute_sharpe returns 0 for empty list."""
        assert _compute_sharpe([]) == Decimal("0")

    def test_compute_sharpe_single(self) -> None:
        """_compute_sharpe returns 0 for single value."""
        assert _compute_sharpe([Decimal("10")]) == Decimal("0")

    def test_compute_sortino_empty(self) -> None:
        """_compute_sortino returns 0 for empty list."""
        assert _compute_sortino([]) == Decimal("0")

    def test_compute_profit_factor_empty(self) -> None:
        """_compute_profit_factor returns 0 for empty list."""
        assert _compute_profit_factor([]) == Decimal("0")

    def test_compute_profit_factor_no_losses(self) -> None:
        """_compute_profit_factor returns high value when no losses."""
        scores = [Decimal("10"), Decimal("12"), Decimal("14")]
        result = _compute_profit_factor(scores)
        assert result > Decimal("100")

    def test_compute_profit_factor_mixed(self) -> None:
        """_compute_profit_factor computes correctly."""
        scores = [Decimal("100"), Decimal("110"), Decimal("90"), Decimal("120")]
        # Gains: 10 + 30 = 40, Losses: 20
        # Profit factor = 40/20 = 2
        result = _compute_profit_factor(scores)
        assert abs(result - Decimal("2")) < Decimal("0.01")


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Priority 3 — Validation Framework
# ═══════════════════════════════════════════════════════════════════════════════

class TestCompareRuns:
    """Tests for the compare_runs domain service (Priority 3)."""

    def test_identical_runs(self) -> None:
        """Comparing identical runs produces no diffs."""
        snapshots = [
            {
                "security_id": 1,
                "symbol": "RELIANCE",
                "rank": 1,
                "momentum_score": Decimal("85.5"),
                "buy_setup_score": Decimal("70.0"),
                "rule_results": (
                    {"rule_id": "r1", "engine_id": "e1", "passed": True, "raw_value": Decimal("100")},
                    {"rule_id": "r2", "engine_id": "e1", "passed": True, "raw_value": Decimal("50")},
                ),
            },
            {
                "security_id": 2,
                "symbol": "TCS",
                "rank": 2,
                "momentum_score": Decimal("75.0"),
                "buy_setup_score": Decimal("65.0"),
                "rule_results": (
                    {"rule_id": "r1", "engine_id": "e1", "passed": True, "raw_value": Decimal("90")},
                    {"rule_id": "r2", "engine_id": "e1", "passed": False, "raw_value": Decimal("30")},
                ),
            },
        ]

        report = compare_runs(
            run_a_snapshots=snapshots,
            run_b_snapshots=snapshots,
            run_id_a=1,
            run_id_b=2,
            run_date_a=date(2024, 1, 1),
            run_date_b=date(2024, 1, 1),
            strategy_name="minervini",
        )

        assert report.is_identical()
        assert report.ranking_changed == 0
        assert report.score_changed == 0
        assert len(report.rule_diffs) == 0
        assert report.common_securities == 2

    def test_different_rankings(self) -> None:
        """Comparing runs with different rankings detects changes."""
        snapshots_a = [
            {
                "security_id": 1,
                "symbol": "RELIANCE",
                "rank": 1,
                "momentum_score": Decimal("85.5"),
                "buy_setup_score": Decimal("70.0"),
                "rule_results": (),
            },
            {
                "security_id": 2,
                "symbol": "TCS",
                "rank": 2,
                "momentum_score": Decimal("75.0"),
                "buy_setup_score": Decimal("65.0"),
                "rule_results": (),
            },
        ]

        snapshots_b = [
            {
                "security_id": 1,
                "symbol": "RELIANCE",
                "rank": 2,
                "momentum_score": Decimal("75.0"),
                "buy_setup_score": Decimal("65.0"),
                "rule_results": (),
            },
            {
                "security_id": 2,
                "symbol": "TCS",
                "rank": 1,
                "momentum_score": Decimal("85.5"),
                "buy_setup_score": Decimal("70.0"),
                "rule_results": (),
            },
        ]

        report = compare_runs(
            run_a_snapshots=snapshots_a,
            run_b_snapshots=snapshots_b,
            run_id_a=1,
            run_id_b=2,
            run_date_a=date(2024, 1, 1),
            run_date_b=date(2024, 2, 1),
            strategy_name="minervini",
        )

        assert not report.is_identical()
        assert report.ranking_changed > 0

    def test_rule_regression_detection(self) -> None:
        """Comparing runs with different rule results detects rule diffs."""
        snapshots_a = [
            {
                "security_id": 1,
                "symbol": "RELIANCE",
                "rank": 1,
                "momentum_score": Decimal("85.5"),
                "buy_setup_score": Decimal("70.0"),
                "rule_results": (
                    {"rule_id": "r1", "engine_id": "e1", "passed": True, "raw_value": Decimal("100")},
                ),
            },
        ]

        snapshots_b = [
            {
                "security_id": 1,
                "symbol": "RELIANCE",
                "rank": 1,
                "momentum_score": Decimal("85.5"),
                "buy_setup_score": Decimal("70.0"),
                "rule_results": (
                    {"rule_id": "r1", "engine_id": "e1", "passed": False, "raw_value": Decimal("50")},
                ),
            },
        ]

        report = compare_runs(
            run_a_snapshots=snapshots_a,
            run_b_snapshots=snapshots_b,
            run_id_a=1,
            run_id_b=2,
            run_date_a=date(2024, 1, 1),
            run_date_b=date(2024, 2, 1),
            strategy_name="minervini",
        )

        assert len(report.rule_diffs) == 1
        assert report.rule_diffs[0].rule_id == "r1"
        assert report.rule_diffs[0].passed_a is True
        assert report.rule_diffs[0].passed_b is False

    def test_empty_run_comparison(self) -> None:
        """Comparing empty runs produces empty report."""
        report = compare_runs(
            run_a_snapshots=[],
            run_b_snapshots=[],
            run_id_a=1,
            run_id_b=2,
            run_date_a=date(2024, 1, 1),
            run_date_b=date(2024, 2, 1),
            strategy_name="minervini",
        )

        assert report.common_securities == 0
        assert report.ranking_changed == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Priority 4 — Strategy Evaluation
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputePerformance:
    """Tests for the compute_performance domain service (Priority 4)."""

    def test_empty_run_summaries(self) -> None:
        """Empty summaries produce empty performance."""
        perf = compute_performance(
            run_summaries=[],
            strategy_id=1,
            strategy_name="minervini",
        )

        assert perf.run_count == 0
        assert perf.strategy_name == "minervini"

    def test_single_run(self) -> None:
        """Single run produces basic metrics."""
        perf = compute_performance(
            run_summaries=[
                {
                    "run_date": date(2024, 1, 1),
                    "total_evaluated": 100,
                    "total_passed": 15,
                    "total_failed": 85,
                    "avg_momentum_score": Decimal("75.5"),
                    "avg_buy_setup_score": Decimal("60.0"),
                },
            ],
            strategy_id=1,
            strategy_name="minervini",
        )

        assert perf.run_count == 1
        assert perf.avg_momentum_score == Decimal("75.5")
        assert perf.avg_buy_setup_score == Decimal("60.0")
        assert perf.max_momentum_score == Decimal("75.5")
        assert perf.min_momentum_score == Decimal("75.5")

    def test_multiple_runs(self) -> None:
        """Multiple runs produce aggregate metrics."""
        perf = compute_performance(
            run_summaries=[
                {
                    "run_date": date(2024, 1, 1),
                    "total_evaluated": 100,
                    "total_passed": 15,
                    "total_failed": 85,
                    "avg_momentum_score": Decimal("80.0"),
                    "avg_buy_setup_score": Decimal("60.0"),
                },
                {
                    "run_date": date(2024, 1, 2),
                    "total_evaluated": 100,
                    "total_passed": 12,
                    "total_failed": 88,
                    "avg_momentum_score": Decimal("70.0"),
                    "avg_buy_setup_score": Decimal("55.0"),
                },
                {
                    "run_date": date(2024, 1, 3),
                    "total_evaluated": 100,
                    "total_passed": 18,
                    "total_failed": 82,
                    "avg_momentum_score": Decimal("90.0"),
                    "avg_buy_setup_score": Decimal("65.0"),
                },
            ],
            strategy_id=1,
            strategy_name="minervini",
        )

        assert perf.run_count == 3
        assert perf.avg_momentum_score == Decimal("80.0")  # (80 + 70 + 90) / 3 = 80
        assert perf.max_momentum_score == Decimal("90.0")
        assert perf.min_momentum_score == Decimal("70.0")
        assert perf.median_momentum_score == Decimal("80.0")

    def test_pass_rate_computed(self) -> None:
        """Pass rate is computed from total_evaluated and total_passed."""
        perf = compute_performance(
            run_summaries=[
                {
                    "run_date": date(2024, 1, 1),
                    "total_evaluated": 100,
                    "total_passed": 25,
                    "total_failed": 75,
                    "avg_momentum_score": Decimal("80.0"),
                    "avg_buy_setup_score": Decimal("60.0"),
                },
            ],
            strategy_id=1,
            strategy_name="minervini",
        )

        assert perf.avg_pass_rate == Decimal("0.25")


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Priority 5 — Contribution Analysis
# ═══════════════════════════════════════════════════════════════════════════════

class TestAnalyzeContribution:
    """Tests for the analyze_contribution domain service (Priority 5)."""

    def test_empty_snapshots(self) -> None:
        """Empty snapshots produce empty report."""
        report = analyze_contribution(
            run_snapshots=[],
            strategy_name="minervini",
            strategy_id=1,
        )

        assert report.run_count == 0
        assert len(report.engine_stats) == 0
        assert len(report.top_rules) == 0

    def test_single_snapshot(self) -> None:
        """Single snapshot produces per-rule stats."""
        report = analyze_contribution(
            run_snapshots=[
                {
                    "run_date": date(2024, 1, 1),
                    "security_id": 1,
                    "rank": 1,
                    "passed": True,
                    "rule_results": (
                        {"rule_id": "r1", "engine_id": "e1", "passed": True, "contribution": Decimal("0.5"), "raw_value": Decimal("100"), "weight": Decimal("1")},
                        {"rule_id": "r2", "engine_id": "e1", "passed": False, "contribution": Decimal("0"), "raw_value": Decimal("20"), "weight": Decimal("1")},
                    ),
                },
            ],
            strategy_name="minervini",
            strategy_id=1,
        )

        assert len(report.engine_stats) > 0
        # Should have at least engine "e1"
        e1_stats = [e for e in report.engine_stats if e.engine_id == "e1"]
        assert len(e1_stats) == 1
        assert len(e1_stats[0].rule_stats) == 2

    def test_redundant_rules_detected(self) -> None:
        """Rules with 100% pass rate are marked as redundant."""
        report = analyze_contribution(
            run_snapshots=[
                {
                    "run_date": date(2024, 1, 1),
                    "security_id": 1,
                    "rank": 1,
                    "passed": True,
                    "rule_results": (
                        {"rule_id": "always_passes", "engine_id": "e1", "passed": True, "contribution": Decimal("0.5"), "raw_value": Decimal("100"), "weight": Decimal("1")},
                    ),
                },
                {
                    "run_date": date(2024, 1, 2),
                    "security_id": 1,
                    "rank": 1,
                    "passed": True,
                    "rule_results": (
                        {"rule_id": "always_passes", "engine_id": "e1", "passed": True, "contribution": Decimal("0.5"), "raw_value": Decimal("100"), "weight": Decimal("1")},
                    ),
                },
            ],
            strategy_name="minervini",
            strategy_id=1,
        )

        redundant_ids = [r.rule_id for r in report.redundant_rules]
        assert "always_passes" in redundant_ids


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Priority 6 — Strategy Comparison
# ═══════════════════════════════════════════════════════════════════════════════

class TestCompareStrategies:
    """Tests for the compare_strategies domain service (Priority 6)."""

    def test_identical_strategies(self) -> None:
        """Comparing identical strategies produces no diffs."""
        snapshots_a = [
            {
                "run_date": date(2024, 1, 1),
                "security_id": 1,
                "symbol": "RELIANCE",
                "rank": 1,
                "momentum_score": Decimal("85.5"),
                "buy_setup_score": Decimal("70.0"),
                "hard_filters_passed": True,
                "rule_results": (
                    {"rule_id": "r1", "engine_id": "e1", "passed": True, "raw_value": Decimal("100")},
                ),
            },
        ]

        report = compare_strategies(
            strategy_a_snapshots=snapshots_a,
            strategy_b_snapshots=snapshots_a,
            strategy_a_name="strategy_a",
            strategy_b_name="strategy_b",
            strategy_a_id=1,
            strategy_b_id=2,
        )

        assert len(report.rule_differences) == 0
        assert report.common_run_dates == 1

    def test_different_scores(self) -> None:
        """Comparing strategies with different scores detects deltas."""
        snapshots_a = [
            {
                "run_date": date(2024, 1, 1),
                "security_id": 1,
                "symbol": "RELIANCE",
                "rank": 1,
                "momentum_score": Decimal("85.5"),
                "buy_setup_score": Decimal("70.0"),
                "hard_filters_passed": True,
                "rule_results": (),
            },
        ]

        snapshots_b = [
            {
                "run_date": date(2024, 1, 1),
                "security_id": 1,
                "symbol": "RELIANCE",
                "rank": 2,
                "momentum_score": Decimal("75.0"),
                "buy_setup_score": Decimal("60.0"),
                "hard_filters_passed": True,
                "rule_results": (),
            },
        ]

        report = compare_strategies(
            strategy_a_snapshots=snapshots_a,
            strategy_b_snapshots=snapshots_b,
            strategy_a_name="strategy_a",
            strategy_b_name="strategy_b",
            strategy_a_id=1,
            strategy_b_id=2,
        )

        assert report.strategy_a_wins_score == 1  # A scored higher
        assert report.strategy_b_wins_score == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Priority 7 — Experiment Framework
# ═══════════════════════════════════════════════════════════════════════════════

class TestApplyParameterOverrides:
    """Tests for the apply_parameter_overrides function (Priority 7)."""

    def test_top_level_override(self) -> None:
        """Top-level parameter overrides are applied correctly."""
        config = {
            "name": "minervini",
            "momentum_weights": {"e1": Decimal("1.0"), "e2": Decimal("1.0")},
            "engines": [],
        }

        overrides = [
            {
                "engine_id": None,
                "rule_id": None,
                "parameter_path": "momentum_weights.e1",
                "new_value": Decimal("2.0"),
            },
        ]

        result = apply_parameter_overrides(config, overrides)
        assert result["momentum_weights"]["e1"] == Decimal("2.0")
        assert result["momentum_weights"]["e2"] == Decimal("1.0")  # Unchanged

    def test_engine_level_override(self) -> None:
        """Engine-level parameter overrides are applied correctly."""
        config = {
            "name": "minervini",
            "engines": [
                {"id": "e1", "enabled": True, "weight": Decimal("1.0"), "rules": []},
            ],
        }

        overrides = [
            {
                "engine_id": "e1",
                "rule_id": None,
                "parameter_path": "weight",
                "new_value": Decimal("2.0"),
            },
        ]

        result = apply_parameter_overrides(config, overrides)
        assert result["engines"][0]["weight"] == Decimal("2.0")

    def test_rule_level_override(self) -> None:
        """Rule-level parameter overrides are applied correctly."""
        config = {
            "name": "minervini",
            "engines": [
                {
                    "id": "e1",
                    "enabled": True,
                    "weight": Decimal("1.0"),
                    "rules": [
                        {"id": "r1", "params": {"norm_min": 70}, "weight": Decimal("1.0")},
                    ],
                },
            ],
        }

        overrides = [
            {
                "engine_id": "e1",
                "rule_id": "r1",
                "parameter_path": "params.norm_min",
                "new_value": 80,
            },
        ]

        result = apply_parameter_overrides(config, overrides)
        assert result["engines"][0]["rules"][0]["params"]["norm_min"] == 80

    def test_original_unchanged(self) -> None:
        """Original config is not mutated by apply_parameter_overrides."""
        config = {
            "name": "minervini",
            "engines": [
                {"id": "e1", "enabled": True, "weight": Decimal("1.0"), "rules": []},
            ],
        }

        overrides = [
            {
                "engine_id": "e1",
                "rule_id": None,
                "parameter_path": "weight",
                "new_value": Decimal("2.0"),
            },
        ]

        apply_parameter_overrides(config, overrides)
        assert config["engines"][0]["weight"] == Decimal("1.0")  # Unchanged


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for domain model construction
# ═══════════════════════════════════════════════════════════════════════════════

class TestDomainModels:
    """Tests that domain models can be constructed correctly."""

    def test_ranking_comparison(self) -> None:
        """RankingComparison model works."""
        rc = RankingComparison(
            security_id=1,
            symbol="RELIANCE",
            run_a_rank=1,
            run_b_rank=2,
            rank_delta=-1,
            run_a_score=Decimal("85.5"),
            run_b_score=Decimal("75.0"),
            score_delta=Decimal("-10.5"),
        )
        assert rc.security_id == 1
        assert rc.symbol == "RELIANCE"
        assert rc.rank_delta == -1

    def test_run_comparison_report_is_identical(self) -> None:
        """RunComparisonReport.is_identical() works."""
        report = RunComparisonReport(
            run_id_a=1,
            run_id_b=2,
            run_date_a=date(2024, 1, 1),
            run_date_b=date(2024, 2, 1),
            strategy_name="minervini",
            common_securities=10,
            ranking_changed=0,
            ranking_unchanged=10,
            ranking_regressed=0,
            ranking_improved=0,
            score_changed=0,
            score_unchanged=10,
            rank_deltas=(),
            score_deltas=(),
            rule_diffs=(),
        )
        assert report.is_identical() is True

    def test_run_comparison_report_not_identical(self) -> None:
        """RunComparisonReport.is_identical() returns False when diffs exist."""
        report = RunComparisonReport(
            run_id_a=1,
            run_id_b=2,
            run_date_a=date(2024, 1, 1),
            run_date_b=date(2024, 2, 1),
            strategy_name="minervini",
            common_securities=10,
            ranking_changed=2,
            ranking_unchanged=8,
            ranking_regressed=1,
            ranking_improved=1,
            score_changed=3,
            score_unchanged=7,
            rank_deltas=(),
            score_deltas=(),
            rule_diffs=(),
        )
        assert report.is_identical() is False

    def test_portfolio_performance_construction(self) -> None:
        """PortfolioPerformance model works."""
        perf = PortfolioPerformance(
            strategy_id=1,
            strategy_name="minervini",
            run_count=10,
            first_run_date=date(2024, 1, 1),
            last_run_date=date(2024, 10, 1),
            avg_momentum_score=Decimal("75.5"),
            median_momentum_score=Decimal("76.0"),
            avg_buy_setup_score=Decimal("60.0"),
            median_buy_setup_score=Decimal("61.0"),
            momentum_score_volatility=Decimal("5.0"),
            buy_setup_score_volatility=Decimal("4.0"),
            max_momentum_score=Decimal("90.0"),
            min_momentum_score=Decimal("50.0"),
            max_drawdown_pct=Decimal("0.15"),
            avg_pass_rate=Decimal("0.20"),
            avg_top_rank_stability=Decimal("0.75"),
            sharpe_ratio=Decimal("1.5"),
            sortino_ratio=Decimal("2.0"),
            profit_factor=Decimal("2.5"),
        )
        assert perf.run_count == 10
        assert perf.sharpe_ratio == Decimal("1.5")

    def test_engine_contribution_stats_pass_rate(self) -> None:
        """EngineContributionStats.avg_pass_rate computes correctly."""
        stats = EngineContributionStats(
            engine_id="e1",
            rule_stats=(
                RuleContributionStats(
                    rule_id="r1", engine_id="e1",
                    run_count=10, pass_count=8, fail_count=2,
                    pass_rate=Decimal("0.8"),
                    avg_contribution=Decimal("0.5"),
                    total_contribution=Decimal("4.0"),
                    avg_raw_value=None,
                    importance_score=Decimal("0.4"),
                ),
                RuleContributionStats(
                    rule_id="r2", engine_id="e1",
                    run_count=10, pass_count=5, fail_count=5,
                    pass_rate=Decimal("0.5"),
                    avg_contribution=Decimal("0.3"),
                    total_contribution=Decimal("1.5"),
                    avg_raw_value=None,
                    importance_score=Decimal("0.15"),
                ),
            ),
            run_count=10,
            avg_engine_score=Decimal("0.4"),
            avg_rules_passed=Decimal("6.5"),
            avg_rules_failed=Decimal("3.5"),
            importance_weight=Decimal("1.0"),
        )
        assert abs(stats.avg_pass_rate - Decimal("0.65")) < Decimal("0.01")

    def test_historical_snapshot(self) -> None:
        """HistoricalSnapshot model works."""
        snapshot = HistoricalSnapshot(
            run_id=1,
            strategy_id=1,
            run_date=date(2024, 1, 1),
            security_id=1,
            symbol="RELIANCE",
            rank=1,
            momentum_score=Decimal("85.5"),
            buy_setup_score=Decimal("70.0"),
            hard_filters_passed=True,
            engine_results={"e1": {"score": Decimal("0.8"), "passed_gate": True, "rules": []}},
            rule_results=({"rule_id": "r1", "passed": True},),
        )
        assert snapshot.run_id == 1
        assert snapshot.symbol == "RELIANCE"

    def test_experiment_config_and_result(self) -> None:
        """ExperimentConfig and ExperimentResult models work."""
        config = ExperimentConfig(
            name="test_experiment",
            description="Test parameter sensitivity",
            base_strategy_name="minervini",
            base_strategy_id=1,
            overrides=(
                ParameterOverride(
                    engine_id="e1",
                    rule_id="r1",
                    parameter_path="params.norm_min",
                    old_value=70,
                    new_value=80,
                ),
            ),
            run_dates=(date(2024, 1, 1), date(2024, 1, 2)),
        )
        assert config.name == "test_experiment"
        assert len(config.overrides) == 1
        assert len(config.run_dates) == 2

        result = ExperimentResult(
            experiment_name="test_experiment",
            variant_name="variant_1",
            overrides=config.overrides,
            config_hash="abc123",
            run_id=1,
            run_date=date(2024, 1, 1),
            total_evaluated=100,
            total_passed=15,
            avg_momentum_score=Decimal("75.0"),
            avg_buy_setup_score=Decimal("60.0"),
        )
        assert result.variant_name == "variant_1"
        assert result.total_passed == 15

    def test_contribution_analysis_report_empty(self) -> None:
        """ContributionAnalysisReport with no data works."""
        report = ContributionAnalysisReport(
            strategy_name="minervini",
            strategy_id=1,
            run_count=0,
            date_range=None,
            engine_stats=(),
            top_rules=(),
            bottom_rules=(),
            redundant_rules=(),
        )
        assert report.run_count == 0
        assert report.date_range is None

    def test_strategy_comparison_report(self) -> None:
        """StrategyComparisonReport model works."""
        report = StrategyComparisonReport(
            strategy_a_name="strategy_a",
            strategy_b_name="strategy_b",
            strategy_a_id=1,
            strategy_b_id=2,
            common_run_dates=5,
            avg_score_delta=Decimal("2.5"),
            median_score_delta=Decimal("2.0"),
            max_score_delta=Decimal("5.0"),
            rank_correlation=Decimal("0.8"),
            score_deltas=(),
            rule_differences=(),
            strategy_a_wins_score=3,
            strategy_b_wins_score=2,
            strategy_a_wins_pass_rate=4,
            strategy_b_wins_pass_rate=1,
        )
        assert report.strategy_a_wins_score == 3
        assert report.rank_correlation == Decimal("0.8")


# ═══════════════════════════════════════════════════════════════════════════════
# Determinism contract tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestResearchDeterminism:
    """Verify that research services produce identical outputs on repeated calls."""

    def test_compare_runs_determinism(self) -> None:
        """compare_runs produces identical results on repeated calls."""
        snapshots_a = [
            {
                "security_id": 1,
                "symbol": "RELIANCE",
                "rank": 1,
                "momentum_score": Decimal("85.5"),
                "buy_setup_score": Decimal("70.0"),
                "rule_results": (
                    {"rule_id": "r1", "engine_id": "e1", "passed": True, "raw_value": Decimal("100")},
                ),
            },
        ]
        snapshots_b = [
            {
                "security_id": 1,
                "symbol": "RELIANCE",
                "rank": 2,
                "momentum_score": Decimal("75.0"),
                "buy_setup_score": Decimal("60.0"),
                "rule_results": (
                    {"rule_id": "r1", "engine_id": "e1", "passed": False, "raw_value": Decimal("80")},
                ),
            },
        ]

        report1 = compare_runs(
            snapshots_a, snapshots_b, 1, 2,
            date(2024, 1, 1), date(2024, 2, 1), "minervini",
        )
        report2 = compare_runs(
            snapshots_a, snapshots_b, 1, 2,
            date(2024, 1, 1), date(2024, 2, 1), "minervini",
        )

        assert report1.ranking_changed == report2.ranking_changed
        assert report1.score_changed == report2.score_changed
        assert len(report1.rule_diffs) == len(report2.rule_diffs)
        assert report1.is_identical() == report2.is_identical()

    def test_apply_overrides_determinism(self) -> None:
        """apply_parameter_overrides produces identical results."""
        config = {
            "name": "minervini",
            "engines": [
                {"id": "e1", "enabled": True, "weight": Decimal("1.0"), "rules": []},
            ],
        }
        overrides = [
            {
                "engine_id": "e1",
                "rule_id": None,
                "parameter_path": "weight",
                "new_value": Decimal("2.0"),
            },
        ]

        result1 = apply_parameter_overrides(config, overrides)
        result2 = apply_parameter_overrides(config, overrides)

        assert result1 == result2