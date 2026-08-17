"""Integration tests for the real, Postgres-backed walk-forward providers.

Exercises ``SqlPriceHistoryProvider`` and ``SqlBenchmarkProvider`` against a
real (test) database, not fakes — the point is to prove the bisect-based
in-memory lookup built from a real SQL load behaves identically to the
in-memory fakes ``test_walk_forward.py`` already validates the runner against.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.infrastructure.persistence.models import (
    BenchmarkIndexDailyModel,
    OHLCVDailyModel,
    SecurityModel,
)
from momentum25.infrastructure.persistence.repositories.walk_forward_market_data import (
    BENCHMARK_LABEL,
    SqlBenchmarkProvider,
    SqlPriceHistoryProvider,
)


async def _seed_security(session: AsyncSession, symbol: str) -> int:
    security = SecurityModel(
        symbol=symbol, name=symbol, exchange="NSE", is_active=True
    )
    session.add(security)
    await session.flush()
    return security.id


@pytest.mark.asyncio
async def test_price_provider_answers_latest_close_on_or_before_horizon(
    db_session: AsyncSession,
) -> None:
    sid = await _seed_security(db_session, "AAA")
    db_session.add_all(
        [
            OHLCVDailyModel(
                security_id=sid,
                date=d,
                open=Decimal(100),
                high=Decimal(101),
                low=Decimal(99),
                close=Decimal(100),
                volume=1000,
                adj_close=Decimal(v),
                adj_factor=Decimal(1),
            )
            for d, v in [
                (date(2024, 1, 2), "10"),
                (date(2024, 1, 5), "11"),
                (date(2024, 1, 10), "12"),
            ]
        ]
    )
    await db_session.commit()

    provider = await SqlPriceHistoryProvider.load(
        db_session, date(2024, 1, 1), date(2024, 1, 31)
    )

    point = provider.price_on_or_before(sid, date(2024, 1, 8), date(2024, 1, 8))
    assert point is not None
    assert point.session_date == date(2024, 1, 5)
    assert point.adj_close == Decimal("11")


@pytest.mark.asyncio
async def test_price_provider_never_looks_past_as_of_even_when_target_is_later(
    db_session: AsyncSession,
) -> None:
    """The as-of horizon wins even if ``target`` names a later date (checklist item 7)."""
    sid = await _seed_security(db_session, "BBB")
    db_session.add_all(
        [
            OHLCVDailyModel(
                security_id=sid,
                date=d,
                open=Decimal(100),
                high=Decimal(101),
                low=Decimal(99),
                close=Decimal(100),
                volume=1000,
                adj_close=Decimal(v),
                adj_factor=Decimal(1),
            )
            for d, v in [(date(2024, 1, 2), "10"), (date(2024, 1, 10), "999")]
        ]
    )
    await db_session.commit()

    provider = await SqlPriceHistoryProvider.load(
        db_session, date(2024, 1, 1), date(2024, 1, 31)
    )

    point = provider.price_on_or_before(sid, date(2024, 1, 10), date(2024, 1, 3))
    assert point is not None
    assert point.session_date == date(2024, 1, 2)
    assert point.adj_close == Decimal("10")


@pytest.mark.asyncio
async def test_price_provider_excludes_rows_with_null_adj_close(
    db_session: AsyncSession,
) -> None:
    """Fail closed: an unadjusted row must never be substituted for a missing adj_close."""
    sid = await _seed_security(db_session, "CCC")
    db_session.add(
        OHLCVDailyModel(
            security_id=sid,
            date=date(2024, 1, 2),
            open=Decimal(100),
            high=Decimal(101),
            low=Decimal(99),
            close=Decimal(100),
            volume=1000,
            adj_close=None,
            adj_factor=Decimal(1),
        )
    )
    await db_session.commit()

    provider = await SqlPriceHistoryProvider.load(
        db_session, date(2024, 1, 1), date(2024, 1, 31)
    )

    assert provider.price_on_or_before(sid, date(2024, 1, 2), date(2024, 1, 2)) is None


@pytest.mark.asyncio
async def test_benchmark_provider_carries_price_index_label(
    db_session: AsyncSession,
) -> None:
    db_session.add_all(
        [
            BenchmarkIndexDailyModel(
                index_code="NIFTY500", date=date(2024, 1, 2), close=Decimal("100")
            ),
            BenchmarkIndexDailyModel(
                index_code="NIFTY500", date=date(2024, 1, 5), close=Decimal("110")
            ),
        ]
    )
    await db_session.commit()

    provider = await SqlBenchmarkProvider.load(
        db_session, "NIFTY500", date(2024, 1, 1), date(2024, 1, 31)
    )

    assert provider.label == BENCHMARK_LABEL == "Nifty 500 Price Index (not TRI)"
    assert provider.level_on_or_before(date(2024, 1, 8), date(2024, 1, 8)) == Decimal("110")
    assert provider.level_on_or_before(date(2024, 1, 3), date(2024, 1, 3)) == Decimal("100")
