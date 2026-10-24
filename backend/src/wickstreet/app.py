"""Composition root of the Wickstreet 2.0 MF application (ADR-023 §2.1, §2.8, U1).

The only place that reads ``mode``: it picks the adapters, and nothing below this
module knows which mode runs. The app is standalone FastAPI with its own lifespan,
middleware and OpenAPI schema. In personal mode ``apphost`` mounts it at
``/api/v1/mf``; it registers every MF route itself (OM-12).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.gzip import GZipMiddleware

from platform_common.database import Database
from platform_common.http import (
    BodySizeLimitMiddleware,
    HostOriginGuardMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
    problem_response,
)
from platform_common.log import get_logger
from wickstreet.analytics.application.research import NoSnapshotError, UnknownFundError
from wickstreet.analytics.domain.calculators import SimulationError
from wickstreet.analytics.domain.screening import CursorError, FilterError
from wickstreet.analytics.interface.http import router as research_router
from wickstreet.config import WickstreetSettings, get_settings
from wickstreet.data_rights.domain.rights import RightsDeniedError
from wickstreet.dependencies import Authenticator
from wickstreet.identity.application.principals import RegisterPrincipal
from wickstreet.identity.infrastructure.local import PERSONAL_CONTEXT, authenticate_local
from wickstreet.identity.infrastructure.registry import SqlPrincipalRegistry
from wickstreet.identity.interface.http import router as identity_router
from wickstreet.mf_data.application.ingest import IngestionBusyError
from wickstreet.mf_data.domain.model import AMFI, REFRESH
from wickstreet.mf_data.infrastructure.scheduler import IST, RefreshScheduler, refresh_due
from wickstreet.persistence.database import check_runtime_role, tenant_transaction
from wickstreet.wiring import Analytics, Ingestion, build_analytics, build_ingestion
from wickstreet.workspace.domain.records import (
    InvalidRecordError,
    UnknownRecordError,
    VersionConflictError,
)
from wickstreet.workspace.interface.http import router as workspace_router

_logger = get_logger("wickstreet.startup")
_ERROR_NAMESPACE = "wickstreet"


class UnsupportedModeError(RuntimeError):
    """The selected mode needs an adapter that is not built yet."""


def _authenticator(settings: WickstreetSettings) -> Authenticator:
    if settings.mode == "personal":
        return authenticate_local
    # Fail closed: SaaS mode needs the OIDC identity adapter (A3 §9), a Phase 2 build.
    raise UnsupportedModeError("WICKSTREET_MODE=saas needs the OIDC identity adapter (Phase 2).")


async def _start_refresh(ingestion: Ingestion, analytics: Analytics) -> RefreshScheduler:
    """Schedule the 11:30 IST refresh and the snapshot after it; catch up once at startup.

    The job refreshes only when today's slot is due, then brings the snapshot up to
    the pointer. A compute is a no-op when the snapshot is current (MF-11).
    """

    async def job() -> None:
        now = datetime.now(IST)
        try:
            status = await ingestion.store.run_status(AMFI, REFRESH, now.date())
            if refresh_due(now, completed_today=status == "completed"):
                summary = await ingestion.refresh.execute(now.date())
                _logger.info("mf_refresh_finished", statuses=dict(summary.statuses))
        except IngestionBusyError:
            _logger.info("mf_refresh_skipped_lock_held")
        except Exception as exc:  # noqa: BLE001 - a failed refresh must not stop the app
            _logger.error("mf_refresh_failed", error=str(exc))
        try:
            outcome = await analytics.compute.execute()
            await analytics.research.warm()
            _logger.info("mf_snapshot", status=outcome.status, revision=outcome.revision)
        except Exception as exc:  # noqa: BLE001 - a failed compute must not stop the app
            _logger.error("mf_snapshot_failed", error=str(exc))

    scheduler = RefreshScheduler(job)
    scheduler.start()
    scheduler.run_now()
    return scheduler


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: WickstreetSettings = app.state.settings
    database: Database = app.state.database
    ingestion: Ingestion | None = None
    scheduler: RefreshScheduler | None = None
    try:
        await check_runtime_role(database)
        if settings.mode == "personal":
            async with tenant_transaction(database, PERSONAL_CONTEXT.tenant_id) as session:
                await RegisterPrincipal(SqlPrincipalRegistry(session)).execute(PERSONAL_CONTEXT)
        if settings.refresh_enabled:
            ingestion = build_ingestion(settings, database)
            scheduler = await _start_refresh(ingestion, app.state.analytics)
        _logger.info("wickstreet_started", mode=settings.mode, refresh=settings.refresh_enabled)
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown()
        if ingestion is not None:
            await ingestion.aclose()
        await database.dispose()


def create_app(settings: WickstreetSettings | None = None) -> FastAPI:
    """Build the MF application for the configured mode."""
    settings = settings or get_settings()
    app = FastAPI(
        title="Wickstreet MF API",
        description="Wickstreet 2.0 mutual-fund research (ADR-022, ADR-023).",
        lifespan=_lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    app.state.settings = settings
    app.state.authenticate = _authenticator(settings)
    app.state.database = Database(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )

    # Compression (acceptance review R-02): NAV series run to hundreds of kB of JSON.
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    # Outermost first, as in Momentum25.
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        HostOriginGuardMiddleware,
        allowed_hosts=settings.allowed_hosts,
        error_namespace=_ERROR_NAMESPACE,
        hosts_setting="WICKSTREET_ALLOWED_HOSTS",
    )
    app.add_middleware(BodySizeLimitMiddleware, error_namespace=_ERROR_NAMESPACE)
    app.add_middleware(RequestContextMiddleware)

    app.state.analytics = build_analytics(settings, app.state.database)
    app.state.research = app.state.analytics.research
    app.include_router(identity_router)
    app.include_router(research_router)
    app.include_router(workspace_router)
    for error, status, title in _PROBLEMS:
        app.add_exception_handler(error, _problem(status, title))
    return app


_PROBLEMS: tuple[tuple[type[Exception], int, str], ...] = (
    (RightsDeniedError, 403, "rights-denied"),
    (FilterError, 422, "invalid-request"),
    (CursorError, 422, "invalid-cursor"),
    (NoSnapshotError, 404, "no-snapshot"),
    (UnknownFundError, 404, "unknown-fund"),
    (SimulationError, 422, "invalid-simulation"),
    (InvalidRecordError, 422, "invalid-record"),
    (UnknownRecordError, 404, "unknown-record"),
    (VersionConflictError, 412, "version-conflict"),
)


def _problem(status: int, title: str) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    """An RFC-7807 handler for one domain error."""

    async def handle(request: Request, exc: Exception) -> JSONResponse:
        return problem_response(
            status, title, str(exc), f"urn:{_ERROR_NAMESPACE}:error:{title}", request.url.path
        )

    return handle
