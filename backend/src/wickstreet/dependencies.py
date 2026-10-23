"""Request-scoped FastAPI dependencies for every MF route.

``current_context`` asks the identity adapter the composition root chose (local in
personal mode). ``tenant_session`` opens the tenant-scoped unit of work. Routes take
both; none reads a tenant id from the request itself.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from wickstreet.context import TenantContext
from wickstreet.persistence.database import tenant_transaction

# Resolves the verified context of a request (local identity, later OIDC).
Authenticator = Callable[[Request], Awaitable[TenantContext]]


async def current_context(request: Request) -> TenantContext:
    """Return the context of the request's verified principal."""
    authenticate: Authenticator = request.app.state.authenticate
    return await authenticate(request)


async def tenant_session(
    request: Request, context: Annotated[TenantContext, Depends(current_context)]
) -> AsyncIterator[AsyncSession]:
    """Yield the request's unit of work, scoped to its tenant."""
    async with tenant_transaction(request.app.state.database, context.tenant_id) as session:
        yield session


Context = Annotated[TenantContext, Depends(current_context)]
TenantSession = Annotated[AsyncSession, Depends(tenant_session)]
