"""Re-screen the live production run (id=12, 2026-08-09) after the live adjustment fix.

Non-destructive: writes under its own ``run_suffix`` so run id=12 (the
pre-fix production run) is untouched. Reuses
:class:`HistoricalScreeningUseCase`, the same driver
``rp014_adjfix_rerun_compare.py`` used for the 64-run comparison, against the
strategy that produced run 12 (``minervini_trend_template``, the frozen
production strategy) so the two runs differ in exactly one input: the
corrected ``adj_factor`` values.

Usage:  python scripts/rp014_reapply_live_run.py
"""

from __future__ import annotations

import asyncio
import json
from datetime import date

from momentum25.application.use_cases.research.forward_returns_backfill import (
    ForwardReturnsBackfill,
)
from momentum25.application.use_cases.research.historical_screening import (
    HistoricalScreeningUseCase,
)
from momentum25.domain.scoring.ranking_engine import RankingEngineImpl
from momentum25.domain.scoring.scoring_engine import ScoringEngineImpl
from momentum25.domain.strategy.bootstrap import register_builtin_engines
from momentum25.domain.strategy.engine_registry import engine_registry
from momentum25.domain.strategy.strategy_engine import StrategyEngine
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.repositories import (
    SqlOHLCVRepository,
    SqlScreeningRunRepository,
    SqlSecurityRepository,
    SqlStrategyRepository,
)
from momentum25.infrastructure.persistence.repositories.benchmark_index import (
    SqlBenchmarkIndexRepository,
)
from momentum25.infrastructure.pipelines.indicator_pipeline import IndicatorPipelineImpl

STRATEGY_NAME = "minervini_trend_template"
RUN_DATE = date(2026, 8, 9)
RUN_SUFFIX = ":adjfix-recheck"


async def main() -> None:
    """Re-screen ``RUN_DATE`` under ``RUN_SUFFIX`` and print the new run id."""
    register_builtin_engines()
    db = get_database()

    async with db.session() as session:
        ohlcv_repo = SqlOHLCVRepository(session)
        screening_run_repo = SqlScreeningRunRepository(session)
        screening_use_case = HistoricalScreeningUseCase(
            security_repo=SqlSecurityRepository(session),
            ohlcv_repo=ohlcv_repo,
            screening_run_repo=screening_run_repo,
            strategy_repo=SqlStrategyRepository(session),
            indicator_pipeline=IndicatorPipelineImpl(session),
            strategy_engine=StrategyEngine(
                engines=engine_registry,
                scoring=ScoringEngineImpl(),
                ranking=RankingEngineImpl(),
            ),
        )
        result = await screening_use_case.execute(
            strategy_name=STRATEGY_NAME,
            as_of_date=RUN_DATE,
            run_suffix=RUN_SUFFIX,
        )
        run_id = int(result["run_id"])

        forward_backfill = ForwardReturnsBackfill(
            screening_run_repo=screening_run_repo,
            ohlcv_repo=ohlcv_repo,
            benchmark_index_repo=SqlBenchmarkIndexRepository(session),
        )
        fr = await forward_backfill.execute(run_id)

    print(
        json.dumps(
            {
                "run_id": run_id,
                "run_date": RUN_DATE.isoformat(),
                "total_evaluated": result["total_evaluated"],
                "total_passed": result["total_passed"],
                "forward_rows": fr["rows_written"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
