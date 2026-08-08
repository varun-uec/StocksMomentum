"""Integration tests for SqlBenchmarkIndexRepository (Objective 7, Benchmark Library).

Covers the real bug this fixes: ``AlphaMeasurementUseCase._get_benchmark_return``
was a hardcoded stub returning ``Decimal("0")`` regardless of real Nifty
50/500 history, silently making every alpha/beta computation compare
against a fabricated flat benchmark.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.ports.market_data import RawIndexBar
from momentum25.infrastructure.persistence.repositories.benchmark_index import (
    SqlBenchmarkIndexRepository,
)


@pytest.mark.asyncio
async def test_get_return_computes_real_close_to_close_return(
    db_session: AsyncSession,
) -> None:
    repo = SqlBenchmarkIndexRepository(db_session)
    await repo.upsert_bars(
        "NIFTY_50",
        [
            RawIndexBar(index_code="NIFTY_50", date=date(2024, 1, 1), close=Decimal("20000")),
            RawIndexBar(index_code="NIFTY_50", date=date(2024, 1, 2), close=Decimal("20400")),
        ],
    )
    await db_session.commit()

    bench_return = await repo.get_return("NIFTY_50", date(2024, 1, 2))
    assert bench_return == Decimal("0.02")  # (20400/20000) - 1


@pytest.mark.asyncio
async def test_get_return_is_none_without_two_prior_closes(
    db_session: AsyncSession,
) -> None:
    repo = SqlBenchmarkIndexRepository(db_session)
    await repo.upsert_bars(
        "NIFTY_500",
        [RawIndexBar(index_code="NIFTY_500", date=date(2024, 1, 1), close=Decimal("20000"))],
    )
    await db_session.commit()

    assert await repo.get_return("NIFTY_500", date(2024, 1, 1)) is None
    assert await repo.get_return("NIFTY_500", date(2024, 6, 1)) is None


@pytest.mark.asyncio
async def test_upsert_bars_is_idempotent(db_session: AsyncSession) -> None:
    repo = SqlBenchmarkIndexRepository(db_session)
    await repo.upsert_bars(
        "NIFTY_50",
        [RawIndexBar(index_code="NIFTY_50", date=date(2024, 1, 1), close=Decimal("20000"))],
    )
    await repo.upsert_bars(
        "NIFTY_50",
        [RawIndexBar(index_code="NIFTY_50", date=date(2024, 1, 1), close=Decimal("20500"))],
    )
    await db_session.commit()

    await repo.upsert_bars(
        "NIFTY_50",
        [RawIndexBar(index_code="NIFTY_50", date=date(2024, 1, 2), close=Decimal("20600"))],
    )
    await db_session.commit()

    bench_return = await repo.get_return("NIFTY_50", date(2024, 1, 2))
    assert bench_return == (Decimal("20600") / Decimal("20500")) - 1
