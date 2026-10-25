"""A second test session must fail before it can reset a shared database."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from tests.database_guard import exclusive_test_database


async def test_second_connection_cannot_enter_destructive_test_fixtures(
    db_engine: AsyncEngine,
) -> None:
    # db_engine's session fixture already owns the guard on its own connection.
    async with db_engine.connect() as connection:
        before = await connection.scalar(text("SELECT count(*) FROM information_schema.tables"))
    with pytest.raises(pytest.UsageError, match="Another test session owns"):
        async with exclusive_test_database(db_engine):
            pytest.fail("second reviewer must not reach schema reset")
    async with db_engine.connect() as connection:
        after = await connection.scalar(text("SELECT count(*) FROM information_schema.tables"))
    assert after == before
