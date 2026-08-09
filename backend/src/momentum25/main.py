"""ASGI application factory: composition root, lifecycle, and wiring.

Builds the FastAPI app, configures logging, registers engines and exception handlers,
syncs strategy definitions into the database, and manages graceful startup/shutdown
of the database, Redis, and scheduler.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from momentum25 import __version__
from momentum25.app.services.screening_job import run_screening_pipeline
from momentum25.domain.strategy.bootstrap import register_builtin_engines
from momentum25.domain.strategy.engine_registry import EngineRegistry, engine_registry
from momentum25.infrastructure.config.settings import Settings, get_settings
from momentum25.infrastructure.config.strategy_loader import load_strategies_dir
from momentum25.infrastructure.logging.setup import configure_logging, get_logger
from momentum25.infrastructure.observability.metrics import (
    db_connection_pool_overflow,
    db_connection_pool_size,
    scheduler_jobs_total,
)
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.repositories import SqlStrategyRepository
from momentum25.infrastructure.redis.client import get_redis_provider
from momentum25.infrastructure.redis.lock import RedisLockFactory
from momentum25.infrastructure.scheduler.scheduler import SchedulerService
from momentum25.interface.api.errors import register_exception_handlers
from momentum25.interface.api.middleware import (
    RateLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from momentum25.interface.api.routers import api_router

_logger = get_logger("startup")

# Graceful shutdown timeout
_SHUTDOWN_TIMEOUT_SECONDS = 30


async def _run_daily_screening_job() -> None:
    """Run the daily screening pipeline for every active strategy.

    Guarded by a Redis distributed lock keyed by today's date so a scaled-out
    deployment with multiple worker processes never runs the job twice for
    the same day (``RedisLockFactory``, written for exactly this case,
    previously had zero callers).
    """
    from datetime import date

    lock_name = f"daily_screening:{date.today().isoformat()}"
    lock_factory = RedisLockFactory(get_redis_provider().client)
    async with lock_factory.acquire(lock_name, timeout_seconds=3600) as acquired:
        if not acquired:
            _logger.info("daily_screening_job_skipped_lock_held", lock=lock_name)
            return

        async with get_database().session() as session:
            strategy_repo = SqlStrategyRepository(session)
            strategies = [
                s for s in await strategy_repo.list() if s.is_active and s.kind == "production"
            ]

        _logger.info("daily_screening_job_started", strategies=[s.name for s in strategies])
        for strategy in strategies:
            try:
                await run_screening_pipeline(strategy.name)
            except Exception as exc:  # noqa: BLE001 - one strategy failing must not stop others
                _logger.error(
                    "daily_screening_job_strategy_failed",
                    strategy=strategy.name,
                    error=str(exc),
                )
        _logger.info("daily_screening_job_completed", strategy_count=len(strategies))


async def _sync_strategies(settings: Settings) -> int:
    """Load strategy JSON files from disk into the database (idempotent upsert).

    Disk is the permanent source of truth: after upserting, every DB strategy
    whose name is not on disk is pruned -- but only when it has no rows in
    ``screening_runs`` (run history is append-only; a strategy with stored runs
    is logged as ``strategy_orphaned_with_runs`` and left alone).

    Returns:
        The number of strategies synced.
    """
    directory = Path(settings.strategy_dir)
    if not directory.exists():
        _logger.warning("strategy_dir_missing", path=str(directory))
        return 0
    strategies = load_strategies_dir(directory)
    async with get_database().session() as session:
        repo = SqlStrategyRepository(session)
        for strategy in strategies:
            await repo.upsert(strategy)
        deleted = await repo.delete_orphans([s.name for s in strategies])
        if deleted:
            _logger.info("strategy_orphans_deleted", names=deleted)
        retained = [
            s.name
            for s in await repo.list()
            if s.name not in {strategy.name for strategy in strategies}
        ]
        if retained:
            _logger.warning("strategy_orphaned_with_runs", names=retained)
    _logger.info("strategies_synced", count=len(strategies))
    return len(strategies)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and graceful shutdown."""
    settings = get_settings()
    configure_logging(level=settings.log_level, json_logs=settings.log_json)

    # Register built-in evaluation engines
    register_builtin_engines()
    engines_registered = len(engine_registry.all_ids())
    app.state.engines_registered = engines_registered
    _logger.info("engines_registered", count=engines_registered)

    # Sync strategies from disk to database
    strategies_loaded = 0
    try:
        strategies_loaded = await _sync_strategies(settings)
    except Exception as exc:  # noqa: BLE001 - startup must surface but not crash wiring
        _logger.error("strategy_sync_failed", error=str(exc))
    app.state.strategies_loaded = strategies_loaded

    # Initialize scheduler. Registration must happen before start() so the
    # job actually exists when SchedulerService logs its post-start job
    # state (Phase 1.4 -- register_daily_job previously had no caller at
    # all, so this scheduler always started with an empty job store).
    scheduler = SchedulerService(settings)
    scheduler.register_daily_job(_run_daily_screening_job)
    app.state.scheduler = scheduler
    scheduler.start()  # no-op unless scheduler_enabled

    # Record database pool metrics
    db_connection_pool_size.set(settings.db_pool_size)
    db_connection_pool_overflow.set(settings.db_max_overflow)

    # Record scheduler metrics. Reports the actual registered job count, not
    # a re-statement of the config flag -- the two previously always agreed
    # only by coincidence (register_daily_job was never called), so this
    # metric was reporting settings.scheduler_enabled under a job-count name.
    scheduler_jobs_total.labels(state="registered").set(scheduler.get_job_count())

    _logger.info("application_started", environment=settings.environment, version=__version__)

    try:
        yield
    finally:
        _logger.info("shutdown_initiated")
        # Graceful shutdown with timeout
        try:
            shutdown_task = asyncio.create_task(_shutdown(scheduler))
            await asyncio.wait_for(shutdown_task, timeout=_SHUTDOWN_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            _logger.warning("shutdown_timeout", timeout_seconds=_SHUTDOWN_TIMEOUT_SECONDS)
        _logger.info("application_stopped")


async def _shutdown(scheduler: SchedulerService) -> None:
    """Perform graceful shutdown of all services."""
    scheduler.shutdown()
    await get_redis_provider().close()
    await get_database().dispose()
    _logger.info("shutdown_complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    app = FastAPI(
        title="Momentum25 India API",
        version=__version__,
        description=(
            "Deterministic, explainable momentum-stock screener for the Indian market. "
            "This build is the architectural foundation; business endpoints return "
            "well-formed placeholder data until later milestones."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    # Middleware order: outermost first (runs last on request, first on response)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        RateLimitMiddleware,
        max_requests=settings.rate_limit_max_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
