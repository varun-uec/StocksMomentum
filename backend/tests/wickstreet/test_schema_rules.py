"""OM-10 and OM-12 against the migrated MF schema.

OM-10: a table in the ``wickstreet`` schema is tenant-scoped unless it is listed as
shared reference data. A tenant-scoped table has a non-null tenant column, forced
row-level security, policies on the tenant setting and an OM-8 case. A user-owned
table also has a non-null ``owner_id``. The two identity tables hold the principals
themselves, so they have no owner column.

OM-12: MF migrations have their own environment and version table, match the MF
models, and leave Momentum25's schema alone.
"""

from __future__ import annotations

import asyncio

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

import wickstreet.identity.infrastructure.tables  # noqa: F401 - registers the tables
from tests.wickstreet.conftest import Urls, alembic_config
from tests.wickstreet.tenant_cases import CASES
from wickstreet.persistence.database import SCHEMA, include_mf_schema, metadata

# Principals: tenant-scoped by these columns, no owner column.
IDENTITY_TABLES = {"tenant": "id", "app_user": "tenant_id"}
# Shared, not tenant-owned (ADR-023 §2.6). List each one; none exists yet.
SHARED_REFERENCE_TABLES: frozenset[str] = frozenset()
_POLICY_SETTING = "current_setting('wickstreet.tenant_id'"


async def violations(connection: AsyncConnection) -> list[str]:
    """Return every OM-10 rule an MF table breaks."""
    tables = (
        await connection.execute(
            text(
                "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity, "
                "  array_remove(array_agg(pg_get_expr(p.polqual, p.polrelid)), NULL), "
                "  array_remove(array_agg(pg_get_expr(p.polwithcheck, p.polrelid)), NULL), "
                "  count(p.oid) "
                "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "LEFT JOIN pg_policy p ON p.polrelid = c.oid "
                "WHERE n.nspname = :schema AND c.relkind IN ('r', 'p') "
                "  AND c.relname <> 'alembic_version' "
                "GROUP BY c.relname, c.relrowsecurity, c.relforcerowsecurity"
            ),
            {"schema": SCHEMA},
        )
    ).all()
    not_null = {
        (table, column)
        for table, column in (
            await connection.execute(
                text(
                    "SELECT c.relname, a.attname FROM pg_attribute a "
                    "JOIN pg_class c ON c.oid = a.attrelid "
                    "JOIN pg_namespace n ON n.oid = c.relnamespace "
                    "WHERE n.nspname = :schema AND a.attnum > 0 AND a.attnotnull "
                    "  AND NOT a.attisdropped"
                ),
                {"schema": SCHEMA},
            )
        ).all()
    }
    found: list[str] = []
    for name, rls, forced, quals, checks, policies in tables:
        if name in SHARED_REFERENCE_TABLES:
            continue
        tenant_column = IDENTITY_TABLES.get(name, "tenant_id")
        required = [tenant_column] if name in IDENTITY_TABLES else [tenant_column, "owner_id"]
        found += [
            f"{name}.{c} is missing or nullable" for c in required if (name, c) not in not_null
        ]
        if not (rls and forced):
            found.append(f"{name} lacks forced row-level security")
        if policies == 0 or not all(_POLICY_SETTING in expr for expr in [*quals, *checks]):
            found.append(f"{name} lacks a policy on the tenant setting")
        if name not in CASES:
            found.append(f"{name} has no OM-8 case in tenant_cases.py")
    return found


async def test_every_mf_table_is_tenant_scoped_or_listed_as_shared(mf_urls: Urls) -> None:
    engine = create_async_engine(mf_urls.owner)
    async with engine.connect() as connection:
        assert await violations(connection) == []
    await engine.dispose()
    assert set(IDENTITY_TABLES) <= set(CASES)


async def test_the_rule_catches_an_unprotected_table(mf_urls: Urls) -> None:
    engine = create_async_engine(mf_urls.owner)
    async with engine.connect() as connection:
        await connection.execute(
            text("CREATE TABLE wickstreet.om10_probe (id uuid, tenant_id uuid)")
        )
        found = await violations(connection)
        await connection.rollback()
    await engine.dispose()
    assert found == [
        "om10_probe.tenant_id is missing or nullable",
        "om10_probe.owner_id is missing or nullable",
        "om10_probe lacks forced row-level security",
        "om10_probe lacks a policy on the tenant setting",
        "om10_probe has no OM-8 case in tenant_cases.py",
    ]


def _model_diff(connection: Connection) -> list[object]:
    context = MigrationContext.configure(
        connection,
        opts={
            "include_schemas": True,
            "include_name": include_mf_schema,
            "version_table_schema": SCHEMA,
        },
    )
    return list(compare_metadata(context, metadata))


async def test_mf_migrations_match_the_mf_models(mf_urls: Urls) -> None:
    engine = create_async_engine(mf_urls.owner)
    async with engine.connect() as connection:
        assert await connection.run_sync(_model_diff) == []
    await engine.dispose()


async def _public_snapshot(engine: AsyncEngine) -> tuple[list[str], list[str]]:
    async with engine.connect() as connection:
        tables = (
            await connection.scalars(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY 1")
            )
        ).all()
        versions: list[str] = []
        if await connection.scalar(text("SELECT to_regclass('public.alembic_version')")):
            versions = list(
                (
                    await connection.scalars(text("SELECT version_num FROM public.alembic_version"))
                ).all()
            )
    return list(tables), versions


async def test_mf_migrations_run_alone_and_leave_momentum25_untouched(
    db_engine: AsyncEngine, mf_urls: Urls
) -> None:
    """Down to base and back up: Momentum25's tables and version rows never change."""
    admin = create_async_engine(mf_urls.admin)
    before = await _public_snapshot(admin)
    config = alembic_config(mf_urls.owner)
    await asyncio.to_thread(command.downgrade, config, "base")
    await asyncio.to_thread(command.upgrade, config, "head")
    after = await _public_snapshot(admin)
    async with admin.connect() as connection:
        mf_version = await connection.scalar(
            text(f"SELECT version_num FROM {SCHEMA}.alembic_version")
        )
    await admin.dispose()
    assert before[0]
    assert after == before
    assert mf_version == "0001_identity_tenancy"
