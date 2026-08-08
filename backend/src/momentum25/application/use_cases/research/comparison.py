"""Strategy Comparison — compare multiple strategy configurations.

Priority 6 of Phase 4. Provides deterministic comparison reports showing
ranking differences, score differences, rule differences, and performance
differences between two strategy configurations.
"""

from __future__ import annotations

from typing import Any

from structlog import get_logger

from momentum25.domain.research.models import StrategyComparisonReport
from momentum25.domain.research.services import compare_strategies

_logger = get_logger("strategy_comparison")


class StrategyComparisonUseCase:
    """Compare the outputs of two strategy configurations.

    Supports comparing:
        - Multiple screening runs under different strategies.
        - Different strategy configurations.
        - Different scoring models.

    All comparisons are deterministic and fully reproducible.
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
        strategy_a_name: str,
        strategy_b_name: str,
        max_runs: int = 20,
    ) -> StrategyComparisonReport:
        """Compare two strategies across their historical runs.

        Args:
            strategy_a_name: Name of the first strategy (baseline).
            strategy_b_name: Name of the second strategy (comparison).
            max_runs: Maximum number of recent runs per strategy to include.

        Returns:
            A StrategyComparisonReport with deterministic diffs.

        Raises:
            ValueError: If either strategy is not found.
        """
        strategy_a = await self._strategy_repo.get_active(strategy_a_name)
        strategy_b = await self._strategy_repo.get_active(strategy_b_name)

        if strategy_a is None:
            raise ValueError(f"Strategy not found: {strategy_a_name}")
        if strategy_b is None:
            raise ValueError(f"Strategy not found: {strategy_b_name}")

        # Build snapshots for both strategies
        snapshots_a = await self._build_strategy_snapshots(
            strategy_a.id or 0, max_runs
        )
        snapshots_b = await self._build_strategy_snapshots(
            strategy_b.id or 0, max_runs
        )

        return compare_strategies(
            strategy_a_snapshots=snapshots_a,
            strategy_b_snapshots=snapshots_b,
            strategy_a_name=strategy_a_name,
            strategy_b_name=strategy_b_name,
            strategy_a_id=strategy_a.id or 0,
            strategy_b_id=strategy_b.id or 0,
        )

    async def _build_strategy_snapshots(
        self,
        strategy_id: int,
        max_runs: int,
    ) -> list[dict[str, Any]]:
        """Build snapshot dicts for all runs of a given strategy."""
        runs, _total = await self._screening_run_repo.list_runs(
            status="COMPLETED", limit=max_runs, offset=0
        )
        strategy_runs = [r for r in runs if r.strategy_id == strategy_id]

        snapshots = []
        for run in strategy_runs:
            rankings, _ = await self._screening_run_repo.get_rankings(
                run.id if run.id else 0, limit=10000, offset=0
            )

            for ranking in rankings:
                rule_results = await self._screening_run_repo.get_rule_results(
                    run.id if run.id else 0, ranking.security_id
                )
                snapshots.append({
                    "run_date": run.run_date,
                    "security_id": ranking.security_id,
                    "symbol": str(ranking.security_id),
                    "rank": ranking.rank,
                    "momentum_score": ranking.momentum_score,
                    "buy_setup_score": ranking.buy_setup_score,
                    "hard_filters_passed": ranking.rank is not None,
                    "rule_results": tuple(
                        {
                            "rule_id": r.rule_id,
                            "engine_id": r.engine_id,
                            "passed": r.passed,
                            "raw_value": r.raw_value,
                            "contribution": r.contribution,
                        }
                        for r in rule_results
                    ),
                })

        return snapshots