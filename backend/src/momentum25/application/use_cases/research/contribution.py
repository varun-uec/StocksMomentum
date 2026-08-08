"""Rule Contribution Analysis — measure rule & engine importance across runs.

Priority 5 of Phase 4. Analyzes individual rule contributions, engine contributions,
rule importance, pass/fail frequency, and identifies redundant rules.
"""

from __future__ import annotations

from typing import Any

from structlog import get_logger

from momentum25.domain.research.models import ContributionAnalysisReport
from momentum25.domain.research.services import analyze_contribution

_logger = get_logger("contribution_analysis")


class ContributionAnalysisUseCase:
    """Analyze rule and engine contribution across multiple historical runs."""

    def __init__(self, screening_run_repo: Any) -> None:
        """Wire the use case.

        Args:
            screening_run_repo: Repository for screening runs and results.
        """
        self._screening_run_repo = screening_run_repo

    async def execute(
        self,
        strategy_id: int,
        strategy_name: str,
        max_runs: int = 20,
    ) -> ContributionAnalysisReport:
        """Analyze rule contribution across runs for a given strategy.

        Args:
            strategy_id: The strategy ID to analyze.
            strategy_name: The strategy name.
            max_runs: Maximum number of recent runs to include.

        Returns:
            A ContributionAnalysisReport with cross-run statistics.
        """
        # Load recent completed runs for this strategy
        runs, _total = await self._screening_run_repo.list_runs(
            status="COMPLETED", limit=max_runs, offset=0
        )
        if strategy_id != 0:
            strategy_runs = [r for r in runs if r.strategy_id == strategy_id]
        else:
            strategy_runs = runs

        if not strategy_runs:
            # Return empty report
            return ContributionAnalysisReport(
                strategy_name=strategy_name,
                strategy_id=strategy_id,
                run_count=0,
                date_range=None,
                engine_stats=(),
                top_rules=(),
                bottom_rules=(),
                redundant_rules=(),
            )

        # Build snapshot dicts for all runs
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
                    "run_id": run.id or 0,
                    "run_date": run.run_date,
                    "security_id": ranking.security_id,
                    "rank": ranking.rank,
                    "momentum_score": ranking.momentum_score,
                    "buy_setup_score": ranking.buy_setup_score,
                    "hard_filters_passed": ranking.rank is not None,
                    "rule_results": tuple(
                        {
                            "rule_id": r.rule_id,
                            "engine_id": r.engine_id,
                            "passed": r.passed,
                            "contribution": r.contribution,
                            "raw_value": r.raw_value,
                            "weight": r.weight,
                        }
                        for r in rule_results
                    ),
                })

        return analyze_contribution(
            run_snapshots=snapshots,
            strategy_name=strategy_name,
            strategy_id=strategy_id,
        )