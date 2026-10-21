"""Alembic environment — async, driven by application settings and ORM metadata."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

from momentum25.infrastructure.config.settings import get_settings
from momentum25.infrastructure.persistence.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject the runtime database URL from settings (keeps secrets out of alembic.ini).
config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = Base.metadata

# Built by migration 0008 with raw SQL: they need the pg_trgm extension, which
# the test schema (``create_all``) does not install, so the models do not declare them.
_RAW_SQL_INDEXES = {"ix_securities_symbol_trgm", "ix_securities_name_trgm"}


def include_object(obj: object, name: str | None, type_: str, *_: object) -> bool:
    """Leave the raw-SQL trigram indexes out of the comparison."""
    return not (type_ == "index" and name in _RAW_SQL_INDEXES)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL without a DB connection)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        include_object=include_object,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: object) -> None:
    context.configure(
        connection=connection,  # type: ignore[arg-type]
        target_metadata=target_metadata,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode with an async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
