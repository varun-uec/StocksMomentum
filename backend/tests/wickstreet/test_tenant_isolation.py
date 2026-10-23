"""OM-8: no tenant can read, list, change, delete or export another tenant's records.

Every check runs as ``wickstreet_app``, the runtime role, so row-level security is
what stops it (ADR-023 §2.6, U3). The API checks run through the real app.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.requests import Request

from momentum25.infrastructure.persistence.models import Base
from platform_common.database import Database
from tests.wickstreet.conftest import Urls
from tests.wickstreet.tenant_cases import CASES
from wickstreet.app import create_app
from wickstreet.config import WickstreetSettings
from wickstreet.context import TenantContext
from wickstreet.identity.application.principals import RegisterPrincipal
from wickstreet.identity.infrastructure.registry import SqlPrincipalRegistry
from wickstreet.persistence.database import (
    TENANT_SETTING,
    UnsafeDatabaseRoleError,
    tenant_transaction,
)
from wickstreet.persistence.roles import ensure_roles

Tenants = tuple[TenantContext, TenantContext]
_RLS = "row-level security"


@pytest.fixture
async def tenants(app_database: Database) -> Tenants:
    """Two synthetic tenants, each with one user, registered as the runtime role."""
    pair = (TenantContext(uuid4(), uuid4()), TenantContext(uuid4(), uuid4()))
    for context in pair:
        async with tenant_transaction(app_database, context.tenant_id) as session:
            await RegisterPrincipal(SqlPrincipalRegistry(session)).execute(context)
    return pair


def _where(key: dict[str, UUID]) -> tuple[str, dict[str, UUID]]:
    return " AND ".join(f"{column} = :{column}" for column in key), key


@pytest.mark.parametrize("table", sorted(CASES))
async def test_a_full_scan_lists_and_exports_only_own_rows(
    app_database: Database, tenants: Tenants, table: str
) -> None:
    mine, _ = tenants
    column = CASES[table].tenant_column
    async with tenant_transaction(app_database, mine.tenant_id) as session:
        owners = (await session.scalars(text(f"SELECT {column} FROM wickstreet.{table}"))).all()
    assert owners
    assert set(owners) == {mine.tenant_id}


@pytest.mark.parametrize("table", sorted(CASES))
async def test_another_tenants_row_cannot_be_read(
    app_database: Database, tenants: Tenants, table: str
) -> None:
    mine, theirs = tenants
    where, params = _where(CASES[table].key(theirs))
    async with tenant_transaction(app_database, mine.tenant_id) as session:
        found = await session.scalar(
            text(f"SELECT count(*) FROM wickstreet.{table} WHERE {where}"), params
        )
    assert found == 0


@pytest.mark.parametrize("table", sorted(CASES))
async def test_another_tenants_row_cannot_be_changed_or_deleted(
    app_database: Database, tenants: Tenants, table: str
) -> None:
    mine, theirs = tenants
    case = CASES[table]
    where, params = _where(case.key(theirs))
    async with tenant_transaction(app_database, mine.tenant_id) as session:
        changed = await session.execute(
            text(
                f"UPDATE wickstreet.{table} SET {case.tenant_column} = {case.tenant_column} "
                f"WHERE {where}"
            ),
            params,
        )
        deleted = await session.execute(
            text(f"DELETE FROM wickstreet.{table} WHERE {where}"), params
        )
    assert (changed.rowcount, deleted.rowcount) == (0, 0)  # type: ignore[attr-defined]
    async with tenant_transaction(app_database, theirs.tenant_id) as session:
        still_there = await session.scalar(
            text(f"SELECT count(*) FROM wickstreet.{table} WHERE {where}"), params
        )
    assert still_there == 1


@pytest.mark.parametrize("table", sorted(CASES))
async def test_a_row_cannot_be_moved_to_another_tenant(
    app_database: Database, tenants: Tenants, table: str
) -> None:
    mine, theirs = tenants
    case = CASES[table]
    where, params = _where(case.key(mine))
    with pytest.raises(DBAPIError, match=_RLS):
        async with tenant_transaction(app_database, mine.tenant_id) as session:
            await session.execute(
                text(f"UPDATE wickstreet.{table} SET {case.tenant_column} = :target WHERE {where}"),
                {**params, "target": theirs.tenant_id},
            )


@pytest.mark.parametrize("table", sorted(CASES))
async def test_a_row_cannot_be_written_for_another_tenant(
    app_database: Database, tenants: Tenants, table: str
) -> None:
    mine, theirs = tenants
    row = CASES[table].forged_row(theirs)
    columns = ", ".join(row)
    values = ", ".join(f":{column}" for column in row)
    with pytest.raises(DBAPIError, match=_RLS):
        async with tenant_transaction(app_database, mine.tenant_id) as session:
            await session.execute(
                text(f"INSERT INTO wickstreet.{table} ({columns}) VALUES ({values})"), row
            )


@pytest.mark.parametrize("table", sorted(CASES))
async def test_without_a_tenant_nothing_is_visible(
    app_database: Database, tenants: Tenants, table: str
) -> None:
    async with app_database.session() as session:
        assert await session.scalar(text(f"SELECT count(*) FROM wickstreet.{table}")) == 0


async def test_the_tenant_setting_ends_with_its_transaction(
    app_database: Database, tenants: Tenants
) -> None:
    """A pooled connection never carries one request's tenant into the next."""
    mine, _ = tenants
    count = text("SELECT count(*) FROM wickstreet.app_user")
    async with app_database.engine.connect() as connection:
        async with connection.begin():
            await connection.execute(
                select(func.set_config(TENANT_SETTING, str(mine.tenant_id), True))
            )
            assert await connection.scalar(count) == 1
        async with connection.begin():
            assert await connection.scalar(count) == 0


async def test_the_runtime_role_cannot_bypass_row_level_security(app_database: Database) -> None:
    async with app_database.engine.connect() as connection:
        superuser, bypass, owned = (
            await connection.execute(
                text(
                    "SELECT rolsuper, rolbypassrls, (SELECT count(*) FROM pg_tables "
                    "WHERE schemaname = 'wickstreet' AND tableowner = current_user) "
                    "FROM pg_roles WHERE rolname = current_user"
                )
            )
        ).one()
    assert (superuser, bypass, owned) == (False, False, 0)


async def test_the_runtime_role_has_no_grant_on_momentum25_tables(
    db_engine: AsyncEngine, app_database: Database
) -> None:
    async with app_database.engine.connect() as connection:
        granted, total = (
            await connection.execute(
                text(
                    "SELECT count(*) FILTER (WHERE has_table_privilege("
                    "format('%I.%I', schemaname, tablename), 'SELECT,INSERT,UPDATE,DELETE')), "
                    "count(*) FROM pg_tables WHERE schemaname = 'public'"
                )
            )
        ).one()
    assert total >= len(Base.metadata.tables)
    assert granted == 0
    with pytest.raises(DBAPIError, match="permission denied"):
        async with app_database.session() as session:
            await session.execute(
                text(f"SELECT 1 FROM public.{Base.metadata.sorted_tables[0].name}")
            )


@pytest.mark.parametrize("login", ["admin", "owner"])
async def test_the_app_refuses_to_start_as_a_role_that_bypasses_rls(
    mf_urls: Urls, login: str
) -> None:
    settings = WickstreetSettings(database_url=getattr(mf_urls, login))
    with pytest.raises(UnsafeDatabaseRoleError), TestClient(create_app(settings)):
        pass


def _client(settings: WickstreetSettings, context: TenantContext) -> TestClient:
    app = create_app(settings)

    async def authenticate(request: Request) -> TenantContext:
        return context

    authenticator: Callable[[Request], Awaitable[TenantContext]] = authenticate
    app.state.authenticate = authenticator
    return TestClient(app, base_url="http://localhost")


async def test_the_api_returns_only_the_callers_principal(
    mf_settings: WickstreetSettings, tenants: Tenants
) -> None:
    mine, theirs = tenants
    with _client(mf_settings, mine) as client:
        response = client.get(
            "/me",
            params={"tenant_id": str(theirs.tenant_id)},
            headers={"X-Tenant-Id": str(theirs.tenant_id)},
        )
    assert response.status_code == 200
    assert response.json() == {"tenant_id": str(mine.tenant_id), "user_id": str(mine.user_id)}


async def test_the_api_refuses_a_user_claimed_by_another_tenant(
    mf_settings: WickstreetSettings, tenants: Tenants
) -> None:
    mine, theirs = tenants
    with _client(mf_settings, TenantContext(theirs.tenant_id, mine.user_id)) as client:
        assert client.get("/me").status_code == 403


async def test_role_setup_is_idempotent_and_accepts_any_password(mf_urls: Urls) -> None:
    """A second run re-applies attributes; quoting survives ':' and quote characters."""
    password = "p:w'd%x"
    app_url = make_url(mf_urls.app).set(password=password).render_as_string(hide_password=False)
    try:
        await ensure_roles(mf_urls.admin, owner_url=mf_urls.owner, app_url=app_url)
        database = Database(app_url)
        async with database.session() as session:
            assert await session.scalar(text("SELECT current_user")) == "wickstreet_app"
        await database.dispose()
    finally:
        await ensure_roles(mf_urls.admin, owner_url=mf_urls.owner, app_url=mf_urls.app)
