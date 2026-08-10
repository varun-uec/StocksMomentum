"""Re-screen the monthly run series after the live adjustment fix, and diff it.

Non-destructive by construction. Every run is written under its own
``run_suffix``, so the pre-fix runs stay in place and the two series sit
side by side under different ``data_version`` values.

The driver is not reimplemented. It reuses ``_run_one_date``,
``month_end_targets`` and ``snap_to_trading_dates`` from
``monthly_forward_returns_backfill``, so the re-run and the original series
differ in exactly one input: the corrected ``adj_factor`` values.

Usage:  python scripts/rp014_adjfix_rerun_compare.py [--limit N]
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date
from typing import Any

from sqlalchemy import select

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
from momentum25.infrastructure.persistence.models import ScreeningRunModel
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

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from monthly_forward_returns_backfill import (  # noqa: E402
    _RUN_SUFFIX as _ORIGINAL_SUFFIX,
    _run_one_date,
    _trading_dates,
    month_end_targets,
    snap_to_trading_dates,
    WINDOW_END,
    WINDOW_START,
)

RERUN_SUFFIX = ":adjfix-recheck"


async def _existing(session: Any, suffix: str) -> set[date]:
    """Return run dates already present under ``suffix``."""
    result = await session.execute(
        select(ScreeningRunModel.run_date).where(
            ScreeningRunModel.data_version.like(f"historical:%{suffix}")
        )
    )
    return set(result.scalars().all())


async def main(limit: int | None) -> None:
    """Re-screen every original run date under the re-check suffix."""
    register_builtin_engines()
    db = get_database()

    async with db.session() as session:
        trading_dates = await _trading_dates(session, WINDOW_START, WINDOW_END)
        original_dates = await _existing(session, _ORIGINAL_SUFFIX)
        done = await _existing(session, RERUN_SUFFIX)

    run_dates = [
        d
        for d in snap_to_trading_dates(
            month_end_targets(WINDOW_START, WINDOW_END), trading_dates
        )
        if d in original_dates
    ]
    if limit is not None:
        run_dates = run_dates[:limit]

    summary: dict[str, Any] = {
        "target_dates": len(run_dates),
        "rerun": 0,
        "skipped_existing": 0,
        "failed": [],
    }

    for run_date in run_dates:
        if run_date in done:
            summary["skipped_existing"] += 1
            continue
        try:
            async with db.session() as session:
                ohlcv_repo = SqlOHLCVRepository(session)
                screening_run_repo = SqlScreeningRunRepository(session)
                await _run_one_date(
                    run_date=run_date,
                    screening_use_case=HistoricalScreeningUseCase(
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
                    ),
                    forward_backfill=ForwardReturnsBackfill(
                        screening_run_repo=screening_run_repo,
                        ohlcv_repo=ohlcv_repo,
                        benchmark_index_repo=SqlBenchmarkIndexRepository(session),
                    ),
                    screening_run_repo=screening_run_repo,
                    run_suffix=RERUN_SUFFIX,
                )
            summary["rerun"] += 1
        except Exception as exc:  # noqa: BLE001 — one bad date must not stop the series
            summary["failed"].append({"date": run_date.isoformat(), "error": str(exc)})

    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    asyncio.run(main(args.limit))
