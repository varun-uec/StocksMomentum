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


async def _sync_strategies(settings: Settings) -> int:
    """Load strategy JSON files from disk into the database (idempotent upsert).

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

    # Initialize scheduler
    scheduler = SchedulerService(settings)
    app.state.scheduler = scheduler
    scheduler.start()  # no-op unless enabled; the daily job is registered in M7

    # Record database pool metrics
    db_connection_pool_size.set(settings.db_pool_size)
    db_connection_pool_overflow.set(settings.db_max_overflow)

    # Record scheduler metrics
    scheduler_jobs_total.labels(state="registered").set(
        1 if settings.scheduler_enabled else 0
    )

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
