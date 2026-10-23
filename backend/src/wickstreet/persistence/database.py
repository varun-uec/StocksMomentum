"""The MF schema, the tenant-scoped unit of work, and the runtime role check.

Every MF table lives in the ``wickstreet`` PostgreSQL schema (ADR-023 §2.8). Tenant
isolation is enforced twice: repositories filter by the context's tenant, and
row-level security policies compare each row with the transaction's tenant setting
(ADR-023 §2.6, U3).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, MutableMapping
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from sqlalchemy import MetaData, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from platform_common.database import Database

SCHEMA = "wickstreet"
OWNER_ROLE = "wickstreet_owner"
APP_ROLE = "wickstreet_app"
# RLS policies read it with current_setting(TENANT_SETTING, true): unset matches no row.
TENANT_SETTING = "wickstreet.tenant_id"

# Explicit names keep migrations and `alembic check` stable.
metadata = MetaData(
    schema=SCHEMA,
    naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    },
)


def include_mf_schema(
    name: str | None, type_: str, parent_names: MutableMapping[Any, str | None]
) -> bool:
    """Alembic filter: compare the MF schema only, never Momentum25's tables."""
    if type_ == "schema":
        return name == SCHEMA
    if type_ == "table":
        return parent_names.get("schema_name") == SCHEMA
    return True


class UnsafeDatabaseRoleError(RuntimeError):
    """The runtime login would bypass row-level security."""


@asynccontextmanager
async def tenant_transaction(database: Database, tenant_id: UUID) -> AsyncIterator[AsyncSession]:
    """Yield one unit of work in which every statement runs as ``tenant_id``.

    The setting is transaction-local: it ends at commit or rollback, so a pooled
    connection never carries one tenant into another request. Repositories never
    commit (A3 §5.1); a statement after an early commit would see no tenant rows.
    """
    async with database.session() as session:
        await session.execute(select(func.set_config(TENANT_SETTING, str(tenant_id), True)))
        yield session


async def check_runtime_role(database: Database) -> None:
    """Refuse a login that is a superuser, has BYPASSRLS, or owns an MF table (U3).

    Each of these bypasses row-level security, so tenant isolation would rest on
    application filters alone.
    """
    async with database.engine.connect() as connection:
        row = (
            await connection.execute(
                text(
                    "SELECT current_user, r.rolsuper, r.rolbypassrls, EXISTS ("
                    "  SELECT 1 FROM pg_tables t"
                    "  WHERE t.schemaname = :schema AND t.tableowner = current_user"
                    ") FROM pg_roles r WHERE r.rolname = current_user"
                ),
                {"schema": SCHEMA},
            )
        ).one()
    user, superuser, bypass_rls, owns_tables = row
    if superuser or bypass_rls or owns_tables:
        raise UnsafeDatabaseRoleError(
            f"Database role {user!r} bypasses row-level security (superuser, BYPASSRLS or "
            f"owner of {SCHEMA} tables). Set WICKSTREET_DATABASE_URL to the {APP_ROLE} login."
        )
