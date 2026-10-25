"""Prevent independent pytest sessions from resetting one shared test database."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

# Database-local, session-scoped; both application suites must use the same key.
_LOCK = 0x5749434B


@asynccontextmanager
async def exclusive_test_database(engine: AsyncEngine) -> AsyncIterator[None]:
    """Fail before fixture mutation if another test session owns this database."""
    name = engine.url.database or ""
    if not name.endswith("_test"):
        raise pytest.UsageError(f"Refusing test database lock for {name!r}: must end in _test.")
    async with engine.connect() as connection:
        acquired = await connection.scalar(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": _LOCK}
        )
        if not acquired:
            raise pytest.UsageError(
                f"Another test session owns {name!r}. Use a separate *_test database via "
                "M25_DATABASE_URL; no schema or data was changed by this session."
            )
        try:
            yield
        finally:
            await connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": _LOCK})
