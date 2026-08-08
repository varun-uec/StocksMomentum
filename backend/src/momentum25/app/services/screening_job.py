"""Shared screening-pipeline entry point (Phase 1.4/1.6).

``ExecuteScreening`` was previously only constructible through the FastAPI DI
generator ``get_execute_screening()`` (``interface/api/dependencies.py``),
whose session is tied to a single HTTP request. Neither the scheduler (no
request in flight) nor a background task (must outlive the request that
started it) can use a per-request session, so this module assembles the same
vertical slice independently and exposes one callable both can share.
"""

from __future__ import annotations

from typing import Any

import httpx
from structlog import get_logger

from momentum25.application.use_cases.screening import ExecuteScreening
from momentum25.domain.scoring.ranking_engine import RankingEngineImpl
from momentum25.domain.scoring.scoring_engine import ScoringEngineImpl
from momentum25.domain.strategy.bootstrap import register_builtin_engines
from momentum25.domain.strategy.engine_registry import engine_registry
from momentum25.domain.strategy.strategy_engine import StrategyEngine
from momentum25.domain.value_objects.types import RunStatus
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.repositories import (
    SqlOHLCVRepository,
    SqlScreeningRunRepository,
    SqlSecurityRepository,
)
from momentum25.infrastructure.pipelines.indicator_pipeline import IndicatorPipelineImpl
from momentum25.infrastructure.providers.bhavcopy import BhavcopyProvider

_logger = get_logger("screening_job")


async def run_screening_pipeline(
    strategy_name: str,
    *,
    force: bool = False,
    run_id: int | None = None,
    target_symbols: list[str] | None = None,
    market_data_provider: Any | None = None,
) -> int:
    """Run the full ingest-and-screen pipeline in its own session.

    Args:
        strategy_name: Name of the strategy to run.
        force: Bypass incremental fetch and re-fetch the full lookback window.
        run_id: If provided, updates this already-created (``PENDING``) run
            row instead of creating a new one -- the background execution
            path (Phase 1.6) creates the row before returning ``202`` to the
            client, then hands its id here.
        target_symbols: Optional symbol subset (mainly for tests).
        market_data_provider: Override the default ``BhavcopyProvider`` (for
            tests, so a background-execution test does not make real NSE
            network calls).

    Returns:
        The id of the completed run.
    """
    register_builtin_engines()
    session = get_database().new_session()
    try:
        market_data_provider = market_data_provider or BhavcopyProvider(httpx.AsyncClient())
        security_repo = SqlSecurityRepository(session)
        ohlcv_repo = SqlOHLCVRepository(session)
        screening_run_repo = SqlScreeningRunRepository(session)
        indicator_pipeline = IndicatorPipelineImpl(session)
        strategy_engine = StrategyEngine(
            engines=engine_registry,
            scoring=ScoringEngineImpl(),
            ranking=RankingEngineImpl(),
        )

        execute = ExecuteScreening(
            market_data_provider=market_data_provider,
            security_repo=security_repo,
            ohlcv_repo=ohlcv_repo,
            screening_run_repo=screening_run_repo,
            indicator_pipeline=indicator_pipeline,
            strategy_engine=strategy_engine,
        )

        try:
            completed_id = await execute.execute(
                strategy_name=strategy_name,
                target_symbols=target_symbols,
                force=force,
                existing_run_id=run_id,
            )
            _logger.info("screening_job_completed", run_id=completed_id, strategy=strategy_name)
            return completed_id
        except Exception as exc:
            _logger.error("screening_job_failed", strategy=strategy_name, error=str(exc))
            # ExecuteScreening can raise before ever reaching the orchestrator
            # (e.g. "no market data"/"strategy not found"), in which case a
            # pre-created PENDING row would otherwise stay PENDING forever --
            # a client polling GET /runs/{id} would wait indefinitely for a
            # run that already failed.
            if run_id is not None:
                await _mark_run_failed(screening_run_repo, run_id, str(exc))
            raise
    finally:
        await session.close()


async def _mark_run_failed(
    screening_run_repo: SqlScreeningRunRepository, run_id: int, error: str
) -> None:
    """Best-effort: mark a pre-created run row FAILED and commit."""
    from datetime import UTC, datetime

    run = await screening_run_repo.get(run_id)
    if run is None:
        return
    run.status = RunStatus.FAILED
    run.finished_at = datetime.now(UTC)
    run.error = error
    await screening_run_repo.update(run)
    session = getattr(screening_run_repo, "_session", None)
    if session is not None:
        await session.commit()
