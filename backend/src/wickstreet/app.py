"""Composition root of the Wickstreet 2.0 MF application (ADR-023 §2.1, §2.8, U1).

The only place that reads ``mode``: it picks the adapters, and nothing below this
module knows which mode runs. The app is standalone FastAPI with its own lifespan,
middleware and OpenAPI schema. In personal mode ``apphost`` mounts it at
``/api/v1/mf``; it registers every MF route itself (OM-12).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from platform_common.database import Database
from platform_common.http import (
    BodySizeLimitMiddleware,
    HostOriginGuardMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from platform_common.log import get_logger
from wickstreet.config import WickstreetSettings, get_settings
from wickstreet.dependencies import Authenticator
from wickstreet.identity.application.principals import RegisterPrincipal
from wickstreet.identity.infrastructure.local import PERSONAL_CONTEXT, authenticate_local
from wickstreet.identity.infrastructure.registry import SqlPrincipalRegistry
from wickstreet.identity.interface.http import router as identity_router
from wickstreet.persistence.database import check_runtime_role, tenant_transaction

_logger = get_logger("wickstreet.startup")
_ERROR_NAMESPACE = "wickstreet"


class UnsupportedModeError(RuntimeError):
    """The selected mode needs an adapter that is not built yet."""


def _authenticator(settings: WickstreetSettings) -> Authenticator:
    if settings.mode == "personal":
        return authenticate_local
    # Fail closed: SaaS mode needs the OIDC identity adapter (A3 §9), a Phase 2 build.
    raise UnsupportedModeError("WICKSTREET_MODE=saas needs the OIDC identity adapter (Phase 2).")


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: WickstreetSettings = app.state.settings
    database: Database = app.state.database
    try:
        await check_runtime_role(database)
        if settings.mode == "personal":
            async with tenant_transaction(database, PERSONAL_CONTEXT.tenant_id) as session:
                await RegisterPrincipal(SqlPrincipalRegistry(session)).execute(PERSONAL_CONTEXT)
        _logger.info("wickstreet_started", mode=settings.mode)
        yield
    finally:
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

    app.include_router(identity_router)
    return app
