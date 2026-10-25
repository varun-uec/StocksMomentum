"""Fixtures for the Wickstreet 2.0 tests: MF roles, schema and migrations.

The MF roles log in to the same test database as Momentum25 (``M25_DATABASE_URL``,
whose name must end in ``_test``). The admin login is Momentum25's, which is the
PostgreSQL image's superuser, as in Compose. Isolation tests run as
``wickstreet_app``, the production runtime role (ADR-023 U3).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from momentum25.infrastructure.config.settings import get_settings as get_momentum25_settings
from platform_common.database import Database
from wickstreet.config import WickstreetSettings
from wickstreet.persistence.database import APP_ROLE, OWNER_ROLE, SCHEMA
from wickstreet.persistence.roles import ensure_roles

_MIGRATIONS = (
    Path(__file__).resolve().parents[2] / "src" / "wickstreet" / "persistence" / "migrations"
)


@dataclass(frozen=True)
class Urls:
    """Logins to the test database."""

    admin: str
    owner: str
    app: str


def _login(url: str, role: str) -> str:
    return make_url(url).set(username=role, password=role).render_as_string(hide_password=False)


def alembic_config(owner_url: str) -> Config:
    """MF Alembic config without the ini file, so it leaves logging alone."""
    config = Config()
    config.set_main_option("script_location", str(_MIGRATIONS))
    config.set_main_option("sqlalchemy.url", owner_url)
    return config


@pytest.fixture(scope="session")
def urls() -> Urls:
    """Admin, owner and app logins to the test database."""
    admin = get_momentum25_settings().database_url
    name = make_url(admin).database or ""
    if not name.endswith("_test"):
        raise pytest.UsageError(
            f"Refusing to build the MF schema in {name!r}: not a test database."
        )
    return Urls(admin=admin, owner=_login(admin, OWNER_ROLE), app=_login(admin, APP_ROLE))


@pytest.fixture(scope="session")
async def mf_schema(urls: Urls, database_session_guard: None) -> Urls:
    """Rebuild the MF schema once per session: roles, schema, migrations to head."""
    admin = create_async_engine(urls.admin)
    async with admin.begin() as connection:
        await connection.execute(text(f'DROP SCHEMA IF EXISTS "{SCHEMA}" CASCADE'))
    await admin.dispose()
    await ensure_roles(urls.admin, owner_url=urls.owner, app_url=urls.app)
    # env.py calls asyncio.run, which needs a thread without a running loop.
    await asyncio.to_thread(command.upgrade, alembic_config(urls.owner), "head")
    return urls


@pytest.fixture
async def mf_urls(mf_schema: Urls) -> Urls:
    """Empty every MF table before the test."""
    admin = create_async_engine(mf_schema.admin)
    async with admin.begin() as connection:
        tables = (
            await connection.scalars(
                text(
                    "SELECT format('%I.%I', schemaname, tablename) FROM pg_tables "
                    "WHERE schemaname = :schema AND tablename <> 'alembic_version'"
                ),
                {"schema": SCHEMA},
            )
        ).all()
        if tables:
            await connection.execute(text(f"TRUNCATE {', '.join(tables)} CASCADE"))
    await admin.dispose()
    return mf_schema


@pytest.fixture
async def app_database(mf_urls: Urls) -> AsyncIterator[Database]:
    """The MF database as the runtime role."""
    database = Database(mf_urls.app)
    yield database
    await database.dispose()


@pytest.fixture
def mf_settings(mf_urls: Urls) -> WickstreetSettings:
    """Personal-mode settings that log in as the runtime role."""
    return WickstreetSettings(database_url=mf_urls.app, migration_database_url=mf_urls.owner)
