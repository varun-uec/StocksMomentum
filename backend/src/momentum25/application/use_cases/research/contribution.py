"""Rule Contribution Analysis — measure rule & engine importance across runs.

Priority 5 of Phase 4. Analyzes individual rule contributions, engine contributions,
rule importance, pass/fail frequency, and identifies redundant rules.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from structlog import get_logger

from momentum25.application.services.evidence_strategy import resolve_evidence_strategy
from momentum25.domain.entities.strategy import Strategy
from momentum25.domain.research.models import ContributionAnalysisReport
from momentum25.domain.research.services import analyze_contribution

_logger = get_logger("contribution_analysis")


class ContributionAnalysisUseCase:
    """Analyze rule and engine contribution across multiple historical runs."""

    def __init__(self, screening_run_repo: Any, strategy_repo: Any) -> None:
        """Wire the use case.

        Args:
            screening_run_repo: Repository for screening runs and results.
            strategy_repo: Repository used to resolve the strategy by name.
        """
        self._screening_run_repo = screening_run_repo
        self._strategy_repo = strategy_repo

    async def execute(
        self,
        strategy_name: str,
        max_runs: int = 20,
        config_hash: str | None = None,
    ) -> ContributionAnalysisReport:
        """Analyze rule contribution across runs for a given strategy.

        The strategy is resolved here, by name, so the report describes the
        strategy the caller asked for. The router previously passed
        ``strategy_id=0``, which meant "no strategy filter" and mixed every
        strategy's runs into one report.

        Args:
            strategy_name: The strategy name to analyze.
            max_runs: Maximum number of recent runs to include.
            config_hash: Exact config version; omitted means the strategy file.

        Returns:
            A ContributionAnalysisReport with cross-run statistics.
        """
        strategy = await resolve_evidence_strategy(self._strategy_repo, strategy_name, config_hash)
        report = await self._analyze(strategy, strategy_name, max_runs)
        return replace(
            report, strategy_version=strategy.version, config_hash=strategy.config_hash
        )

    async def _analyze(
        self, strategy: Strategy, strategy_name: str, max_runs: int
    ) -> ContributionAnalysisReport:
        strategy_id = strategy.id or 0
        strategy_runs, _total = await self._screening_run_repo.list_runs(
            status="COMPLETED",
            limit=max_runs,
            offset=0,
            strategy_id=strategy_id,
            config_hash=strategy.config_hash,
        )

        if not strategy_runs:
            # Return empty report
            return ContributionAnalysisReport(
                strategy_name=strategy_name,
                strategy_id=strategy_id,
                run_count=0,
                security_count=0,
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
            # One query per run, not one per security.
            rules_by_security = await self._screening_run_repo.get_rule_results_bulk(
                run.id if run.id else 0, [r.security_id for r in rankings]
            )

            for ranking in rankings:
                rule_results = rules_by_security.get(ranking.security_id, [])
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