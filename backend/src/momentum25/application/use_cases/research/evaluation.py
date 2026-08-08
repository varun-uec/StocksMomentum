"""Strategy Evaluation — compute deterministic performance metrics across runs.

Priority 4 of Phase 4. Computes win rate, average/median return, max drawdown,
volatility, Sharpe/Sortino ratios, profit factor, and rank stability.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from structlog import get_logger

from momentum25.domain.research.models import (
    HistoricalRunSummary,
    PortfolioPerformance,
    StrategyEvaluationResult,
)
from momentum25.domain.research.services import compute_performance

_logger = get_logger("strategy_evaluation")


class EvaluateStrategyUseCase:
    """Compute deterministic performance metrics for a strategy across runs.

    The framework is designed so new evaluation metrics can be added without
    modifying existing components — simply add a new function to the domain
    services and call it here.
    """

    def __init__(self, screening_run_repo: Any, strategy_repo: Any) -> None:
        """Wire the use case.

        Args:
            screening_run_repo: Repository for screening runs and results.
            strategy_repo: Repository for strategy definitions.
        """
        self._screening_run_repo = screening_run_repo
        self._strategy_repo = strategy_repo

    async def execute(
        self,
        strategy_name: str,
        max_runs: int = 50,
        date_from: date | None = None,
        date_to: date | None = None,
    ) -> StrategyEvaluationResult:
        """Evaluate a strategy's performance across historical runs.

        Args:
            strategy_name: Name of the strategy to evaluate.
            max_runs: Maximum number of recent runs to include.
            date_from: Optional start date filter.
            date_to: Optional end date filter.

        Returns:
            A StrategyEvaluationResult with performance metrics.

        Raises:
            ValueError: If the strategy is not found.
        """
        strategy = await self._strategy_repo.get_active(strategy_name)
        if strategy is None:
            raise ValueError(f"Strategy not found: {strategy_name}")

        # Load runs
        runs, _total = await self._screening_run_repo.list_runs(
            status="COMPLETED", limit=max_runs, offset=0
        )

        # Filter runs by strategy
        strategy_runs = [r for r in runs if r.strategy_id == (strategy.id or 0)]

        # Apply date filters
        if date_from:
            strategy_runs = [r for r in strategy_runs if r.run_date >= date_from]
        if date_to:
            strategy_runs = [r for r in strategy_runs if r.run_date <= date_to]

        if not strategy_runs:
            # Return empty result
            empty_performance = PortfolioPerformance(
                strategy_id=strategy.id or 0,
                strategy_name=strategy_name,
                run_count=0,
                first_run_date=None,
                last_run_date=None,
                avg_momentum_score=Decimal("0"),
                median_momentum_score=Decimal("0"),
                avg_buy_setup_score=Decimal("0"),
                median_buy_setup_score=Decimal("0"),
                momentum_score_volatility=Decimal("0"),
                buy_setup_score_volatility=Decimal("0"),
                max_momentum_score=Decimal("0"),
                min_momentum_score=Decimal("0"),
                max_drawdown_pct=Decimal("0"),
                avg_pass_rate=Decimal("0"),
                avg_top_rank_stability=Decimal("0"),
                sharpe_ratio=Decimal("0"),
                sortino_ratio=Decimal("0"),
                profit_factor=Decimal("0"),
            )
            return StrategyEvaluationResult(
                strategy_name=strategy_name,
                strategy_id=strategy.id or 0,
                performance=empty_performance,
                run_summaries=(),
                score_history=(),
            )

        # Build run summaries for performance computation
        run_summaries = []
        for run in strategy_runs:
            # Get rankings for this run to compute averages
            rankings, _ = await self._screening_run_repo.get_rankings(
                run.id if run.id else 0, limit=10000, offset=0
            )

            if not rankings:
                continue

            avg_momentum = sum(
                (r.momentum_score for r in rankings), Decimal("0")
            ) / len(rankings)
            avg_buy_setup = sum(
                (r.buy_setup_score for r in rankings), Decimal("0")
            ) / len(rankings)

            stats = run.stats or {}
            run_summaries.append({
                "run_date": run.run_date,
                "total_evaluated": stats.get("total_evaluated", len(rankings)),
                "total_passed": stats.get("total_passed", 0),
                "total_failed": stats.get("total_failed", 0),
                "avg_momentum_score": avg_momentum,
                "avg_buy_setup_score": avg_buy_setup,
            })

        # Compute performance metrics
        performance = compute_performance(
            run_summaries=run_summaries,
            strategy_id=strategy.id or 0,
            strategy_name=strategy_name,
        )

        # Build score history
        score_history = []
        for run in strategy_runs[:10]:  # Limit to last 10 runs for history
            rankings, _ = await self._screening_run_repo.get_rankings(
                run.id if run.id else 0, limit=100, offset=0
            )
            ranked = [r for r in rankings if r.rank is not None]
            for ranking in ranked[:20]:  # Top 20 per run
                score_history.append({
                    "run_date": run.run_date,
                    "security_id": ranking.security_id,
                    "rank": ranking.rank,
                    "momentum_score": ranking.momentum_score,
                    "buy_setup_score": ranking.buy_setup_score,
                })

        return StrategyEvaluationResult(
            strategy_name=strategy_name,
            strategy_id=strategy.id or 0,
            performance=performance,
            run_summaries=tuple(
                HistoricalRunSummary(
                    run_id=r.id or 0,
                    strategy_id=r.strategy_id,
                    strategy_name=strategy_name,
                    run_date=r.run_date,
                    data_version=r.data_version,
                    config_hash=r.config_hash,
                    total_evaluated=(r.stats or {}).get("total_evaluated", 0),
                    total_passed=(r.stats or {}).get("total_passed", 0),
                    total_failed=(r.stats or {}).get("total_failed", 0),
                    started_at=r.started_at,
                    finished_at=r.finished_at,
                    stats=r.stats or {},
                )
                for r in strategy_runs
            ),
            score_history=tuple(score_history),
        )