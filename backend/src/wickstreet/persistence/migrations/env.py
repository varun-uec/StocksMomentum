"""Alembic environment for the MF schema only (ADR-023 §2.8, OM-12).

Runs as ``wickstreet_owner``. Its version table is ``wickstreet.alembic_version``,
and it compares only the ``wickstreet`` schema, so Momentum25's tables and
migration history are invisible to it.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

import wickstreet.data_rights.infrastructure.tables  # noqa: F401 - registers the tables
import wickstreet.identity.infrastructure.tables  # noqa: F401
import wickstreet.mf_data.infrastructure.tables  # noqa: F401
from wickstreet.config import get_settings
from wickstreet.persistence.database import SCHEMA, include_mf_schema, metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# A URL set by the caller (tests) wins; otherwise the owner login from settings.
url = config.get_main_option("sqlalchemy.url") or get_settings().migration_database_url


def _configure(**kwargs: object) -> None:
    context.configure(
        target_metadata=metadata,
        version_table_schema=SCHEMA,
        include_schemas=True,
        include_name=include_mf_schema,
        **kwargs,  # type: ignore[arg-type]
    )


def run_migrations_offline() -> None:
    """Emit SQL without a database connection."""
    _configure(url=url, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def _run(connection: Connection) -> None:
    _configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations with an async engine."""
    engine = create_async_engine(url, poolclass=NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(_run)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
