"""PostgreSQL principal registry.

Each query names the context's tenant, and row-level security applies the same
rule again, so a wrong tenant finds nothing (ADR-023 §2.6).
"""

from __future__ import annotations

from sqlalchemy import exists, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from wickstreet.context import TenantContext
from wickstreet.identity.infrastructure.tables import app_user, tenant


class SqlPrincipalRegistry:
    """Principal registry over a tenant-scoped session (``tenant_transaction``)."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind the registry to the unit of work's session."""
        self._session = session

    async def register(self, context: TenantContext) -> None:
        """Insert the tenant and the user unless they exist."""
        await self._session.execute(
            insert(tenant).values(id=context.tenant_id).on_conflict_do_nothing()
        )
        await self._session.execute(
            insert(app_user)
            .values(id=context.user_id, tenant_id=context.tenant_id)
            .on_conflict_do_nothing()
        )

    async def contains(self, context: TenantContext) -> bool:
        """Return whether the user exists in the context's tenant."""
        found = await self._session.scalar(
            select(
                exists().where(
                    app_user.c.id == context.user_id,
                    app_user.c.tenant_id == context.tenant_id,
                )
            )
        )
        return bool(found)
