"""Migrations build the schema the models declare (R3-B-15).

An empty scratch database is migrated to head, then ``alembic check`` compares it
with the models. Any difference fails the test, so a model change needs a migration.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.sql import text

from momentum25.infrastructure.config.settings import get_settings

_BACKEND = Path(__file__).resolve().parents[2]
_SCRATCH_SUFFIX = "_migrations_test"


async def _admin(url: str, statement: str) -> None:
    engine = create_async_engine(url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(text(statement))
    await engine.dispose()


def _alembic(url: str, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "M25_DATABASE_URL": url}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=_BACKEND,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_migrated_empty_database_matches_the_models() -> None:
    """``upgrade head`` on an empty database leaves nothing for ``alembic check``."""
    base = make_url(get_settings().database_url)
    scratch = base.set(database=f"{base.database}{_SCRATCH_SUFFIX}")
    admin_url = base.set(database="postgres").render_as_string(hide_password=False)
    scratch_url = scratch.render_as_string(hide_password=False)
    asyncio.run(_admin(admin_url, f'DROP DATABASE IF EXISTS "{scratch.database}"'))
    asyncio.run(_admin(admin_url, f'CREATE DATABASE "{scratch.database}"'))
    try:
        upgrade = _alembic(scratch_url, "upgrade", "head")
        assert upgrade.returncode == 0, upgrade.stderr[-2000:]
        check = _alembic(scratch_url, "check")
        assert check.returncode == 0, check.stdout[-2000:] + check.stderr[-2000:]
    finally:
        asyncio.run(_admin(admin_url, f'DROP DATABASE IF EXISTS "{scratch.database}"'))
