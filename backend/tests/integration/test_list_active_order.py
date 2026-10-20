"""Active securities come back in a fixed order, whatever the heap order."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.entities.security import Security
from momentum25.domain.value_objects.types import Symbol
from momentum25.infrastructure.persistence.repositories import SqlSecurityRepository


async def test_list_active_is_ordered_by_id_after_an_update_moves_a_row(
    db_session: AsyncSession,
) -> None:
    # Regression R3-B: list_active had no ORDER BY. Universe RS ratings rank
    # equal returns in input order, so heap order (changed by any UPDATE or a
    # restore) could change a rating for identical inputs.
    repo = SqlSecurityRepository(db_session)
    await repo.upsert_many(
        [Security(symbol=Symbol(s), name=s, is_active=True) for s in ("AAA", "BBB", "CCC")]
    )
    await db_session.commit()
    # An UPDATE writes a new tuple at the end of the heap: AAA now scans last.
    await db_session.execute(text("UPDATE securities SET name = 'AAA2' WHERE symbol = 'AAA'"))
    await db_session.commit()

    ids = [s.id for s in await repo.list_active()]

    assert ids == sorted(ids)
