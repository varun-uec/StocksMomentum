"""Validation Framework — compare runs, detect regressions, verify determinism.

Priority 3 of Phase 4. Provides tools for comparing historical screening runs,
detecting ranking/scoring/rule regressions, and verifying that code changes
do not silently alter historical results.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from structlog import get_logger

from momentum25.domain.research.models import RunComparisonReport
from momentum25.domain.research.services import compare_runs

_logger = get_logger("validation_framework")


class ValidateRunComparisonUseCase:
    """Compare two historical screening runs and produce a deterministic diff.

    Detects ranking regressions, scoring regressions, and rule regressions.
    """

    def __init__(self, screening_run_repo: Any) -> None:
        """Wire the use case with its collaborators.

        Args:
            screening_run_repo: Repository for screening runs and results.
        """
        self._screening_run_repo = screening_run_repo

    async def execute(
        self,
        run_id_a: int,
        run_id_b: int,
    ) -> RunComparisonReport:
        """Compare two runs and produce a deterministic report.

        Args:
            run_id_a: ID of the first (baseline) run.
            run_id_b: ID of the second (comparison) run.

        Returns:
            A RunComparisonReport with all diffs.

        Raises:
            ValueError: If either run is not found.
        """
        # Load both runs
        run_a = await self._screening_run_repo.get(run_id_a)
        run_b = await self._screening_run_repo.get(run_id_b)

        if run_a is None:
            raise ValueError(f"Run {run_id_a} not found")
        if run_b is None:
            raise ValueError(f"Run {run_id_b} not found")

        # Load rankings and rule results for both runs
        rankings_a, _ = await self._screening_run_repo.get_rankings(
            run_id_a, limit=10000, offset=0
        )
        rankings_b, _ = await self._screening_run_repo.get_rankings(
            run_id_b, limit=10000, offset=0
        )

        # Build snapshot dicts for the domain service
        snapshots_a = await self._build_snapshots(run_id_a, rankings_a)
        snapshots_b = await self._build_snapshots(run_id_b, rankings_b)

        strategy_name = f"strategy_{run_a.strategy_id}"

        return compare_runs(
            run_a_snapshots=snapshots_a,
            run_b_snapshots=snapshots_b,
            run_id_a=run_id_a,
            run_id_b=run_id_b,
            run_date_a=run_a.run_date,
            run_date_b=run_b.run_date,
            strategy_name=strategy_name,
        )

    async def _build_snapshots(
        self,
        run_id: int,
        rankings: list[Any],
    ) -> list[dict[str, Any]]:
        """Build snapshot dicts from rankings and rule results."""
        snapshots = []
        for ranking in rankings:
            rule_results = await self._screening_run_repo.get_rule_results(
                run_id, ranking.security_id
            )
            snapshots.append({
                "security_id": ranking.security_id,
                "symbol": str(ranking.security_id),
                "rank": ranking.rank,
                "momentum_score": ranking.momentum_score,
                "buy_setup_score": ranking.buy_setup_score,
                "rule_results": [
                    {
                        "rule_id": r.rule_id,
                        "engine_id": r.engine_id,
                        "passed": r.passed,
                        "raw_value": r.raw_value,
                        "contribution": r.contribution,
                    }
                    for r in rule_results
                ],
            })
        return snapshots


class DeterminismVerificationUseCase:
    """Verify that a run is deterministic by re-running and comparing.

    Executes the same screening twice and verifies identical outputs.
    """

    def __init__(self, historical_screening_use_case: Any) -> None:
        """Wire the use case.

        Args:
            historical_screening_use_case: The historical screening use case.
        """
        self._historical_screening = historical_screening_use_case

    async def verify(
        self,
        strategy_name: str,
        as_of_date: date,
        symbol_filter: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run the same screening twice and verify identical results.

        Args:
            strategy_name: Name of the strategy to test.
            as_of_date: The historical date to screen.
            symbol_filter: Optional symbol filter.

        Returns:
            A dict with keys: run_id_a, run_id_b, is_deterministic, diffs.
        """
        import time
        ts = int(time.time())
        # First run
        result_a = await self._historical_screening.execute(
            strategy_name, as_of_date, symbol_filter, run_suffix=f":det_a_{ts}"
        )
        # Second run (should produce identical results)
        result_b = await self._historical_screening.execute(
            strategy_name, as_of_date, symbol_filter, run_suffix=f":det_b_{ts}"
        )

        # Compare
        compare_use_case = ValidateRunComparisonUseCase(
            self._historical_screening._screening_run_repo
        )
        report = await compare_use_case.execute(
            result_a["run_id"], result_b["run_id"]
        )

        return {
            "run_id_a": result_a["run_id"],
            "run_id_b": result_b["run_id"],
            "is_deterministic": report.is_identical(),
            "diffs": {
                "ranking_changed": report.ranking_changed,
                "score_changed": report.score_changed,
                "rule_diffs": len(report.rule_diffs),
            },
        }