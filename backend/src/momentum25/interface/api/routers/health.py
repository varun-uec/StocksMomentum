"""Health, readiness, liveness, startup probes, and metrics endpoint."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Response
from sqlalchemy import text

from momentum25 import __version__
from momentum25.application.dto.health import (
    HealthDTO,
    LivenessDTO,
    ReadinessDTO,
    StartupDTO,
)
from momentum25.infrastructure.config.settings import get_settings
from momentum25.infrastructure.observability.metrics import metrics_endpoint
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.repositories import SqlOHLCVRepository
from momentum25.infrastructure.redis.client import get_redis_provider

router = APIRouter(tags=["health"])

# Track application start time for uptime calculation
_STARTED_AT = datetime.now(timezone.utc)


@router.get("/health", response_model=HealthDTO)
async def health() -> HealthDTO:
    """Return service health including DB and Redis status (legacy combined endpoint)."""
    db_status = "ok"
    latest = None
    try:
        async with get_database().session() as session:
            await session.execute(text("SELECT 1"))
            latest = await SqlOHLCVRepository(session).latest_date()
    except Exception:  # noqa: BLE001 - health must never raise
        db_status = "error"

    redis_status = "ok"
    try:
        await get_redis_provider().ping()
    except Exception:  # noqa: BLE001
        redis_status = "error"

    overall = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"
    return HealthDTO(
        status=overall,
        db=db_status,
        redis=redis_status,
        latest_run=latest,
        version=__version__,
    )


@router.get("/health/live", response_model=LivenessDTO)
async def liveness() -> LivenessDTO:
    """Kubernetes liveness probe — confirms the process is alive.

    Returns immediately without checking dependencies. If this endpoint is
    unreachable, Kubernetes will restart the pod.
    """
    uptime = (datetime.now(timezone.utc) - _STARTED_AT).total_seconds()
    return LivenessDTO(
        status="ok",
        version=__version__,
        uptime_seconds=round(uptime, 2),
        started_at=_STARTED_AT,
    )


@router.get("/health/ready", response_model=ReadinessDTO)
async def readiness() -> ReadinessDTO:
    """Kubernetes readiness probe — confirms dependencies are reachable.

    Checks database and Redis connectivity. If this endpoint returns non-200,
    Kubernetes will stop routing traffic to this pod.
    """
    db_status = "ok"
    try:
        async with get_database().session() as session:
            await session.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_status = "error"

    redis_status = "ok"
    try:
        await get_redis_provider().ping()
    except Exception:  # noqa: BLE001
        redis_status = "error"

    overall = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"
    return ReadinessDTO(
        status=overall,
        db=db_status,
        redis=redis_status,
        version=__version__,
    )


@router.get("/health/startup", response_model=StartupDTO)
async def startup(request: Request) -> StartupDTO:
    """Kubernetes startup probe — confirms initialization completed successfully.

    Checks that strategies were synced and engines registered during startup.
    """
    app_state = request.app.state
    strategies_loaded = getattr(app_state, "strategies_loaded", 0)
    engines_registered = getattr(app_state, "engines_registered", 0)

    # During startup, successful registration should have ≥ 1 engine registered
    status = "ok" if engines_registered > 0 else "initializing"
    return StartupDTO(
        status=status,
        version=__version__,
        strategies_loaded=strategies_loaded,
        engines_registered=engines_registered,
    )


@router.get("/metrics")
async def metrics() -> Response:
    """Prometheus metrics endpoint.

    Returns all registered metrics in Prometheus text format.
    Configure your Prometheus server to scrape this endpoint.
    """
    payload, headers = metrics_endpoint()
    return Response(content=payload, media_type=headers["content-type"])