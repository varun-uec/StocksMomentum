"""Symbol search must rank the obvious answer first and stay deterministic."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.infrastructure.persistence.models import SecurityModel
from momentum25.infrastructure.persistence.repositories import SqlSecurityRepository


async def _seed(session: AsyncSession) -> None:
    session.add_all(
        [
            SecurityModel(symbol="RELIANCE", name="Reliance Industries Limited", is_active=True),
            SecurityModel(symbol="RELAXO", name="Relaxo Footwears Limited", is_active=True),
            SecurityModel(symbol="RCOM", name="Reliance Communications Limited", is_active=True),
            SecurityModel(symbol="RELDEAD", name="Reliance Delisted", is_active=False),
            SecurityModel(symbol="TCS", name="Tata Consultancy Services", is_active=True),
        ]
    )
    await session.flush()


@pytest.mark.asyncio
async def test_search_ranks_exact_then_prefix_then_name(db_session: AsyncSession) -> None:
    await _seed(db_session)
    repo = SqlSecurityRepository(db_session)

    symbols = [str(s.symbol) for s in await repo.search("REL", 10)]

    # Exact symbol first, then symbol prefixes alphabetically, then name matches.
    assert symbols[0] == "RELAXO"  # no exact match for "REL"; prefixes lead
    assert symbols == ["RELAXO", "RELIANCE", "RCOM"]

    exact = [str(s.symbol) for s in await repo.search("RELIANCE", 10)]
    assert exact[0] == "RELIANCE"


@pytest.mark.asyncio
async def test_search_is_case_insensitive_and_excludes_inactive(
    db_session: AsyncSession,
) -> None:
    await _seed(db_session)
    repo = SqlSecurityRepository(db_session)

    symbols = [str(s.symbol) for s in await repo.search("reliance", 10)]

    assert "RELIANCE" in symbols
    # An inactive listing must never be offered as a destination.
    assert "RELDEAD" not in symbols


@pytest.mark.asyncio
async def test_search_honours_limit_and_blank_query(db_session: AsyncSession) -> None:
    await _seed(db_session)
    repo = SqlSecurityRepository(db_session)

    assert len(await repo.search("REL", 2)) == 2
    assert await repo.search("   ", 10) == []
