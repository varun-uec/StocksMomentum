"""Benchmark-index repository — persistence for Nifty 50/500 daily closes."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.ports.market_data import RawIndexBar
from momentum25.infrastructure.persistence.models import BenchmarkIndexDailyModel


class SqlBenchmarkIndexRepository:
    """Async SQLAlchemy implementation of :class:`BenchmarkIndexRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind the repository to a unit-of-work session."""
        self._session = session

    async def upsert_bars(self, index_code: str, bars: list[RawIndexBar]) -> int:
        """Insert or update benchmark index bars; return the number written."""
        if not bars:
            return 0
        rows = [{"index_code": index_code, "date": b.date, "close": b.close} for b in bars]
        stmt = insert(BenchmarkIndexDailyModel).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[BenchmarkIndexDailyModel.index_code, BenchmarkIndexDailyModel.date],
            set_={"close": stmt.excluded.close},
        )
        await self._session.execute(stmt)
        return len(rows)

    async def get_return(self, index_code: str, as_of: date) -> Decimal | None:
        """Return the index's close-to-close return ending on ``as_of``, or ``None``."""
        result = await self._session.execute(
            select(BenchmarkIndexDailyModel)
            .where(
                BenchmarkIndexDailyModel.index_code == index_code,
                BenchmarkIndexDailyModel.date <= as_of,
            )
            .order_by(BenchmarkIndexDailyModel.date.desc())
            .limit(2)
        )
        rows = result.scalars().all()
        if len(rows) < 2 or rows[1].close <= 0:
            return None
        latest, prior = rows[0], rows[1]
        return (latest.close / prior.close) - 1

    async def get_close(self, index_code: str, as_of: date) -> Decimal | None:
        """Return the index's close on or before ``as_of``, or ``None`` if none exists."""
        result = await self._session.execute(
            select(BenchmarkIndexDailyModel)
            .where(
                BenchmarkIndexDailyModel.index_code == index_code,
                BenchmarkIndexDailyModel.date <= as_of,
            )
            .order_by(BenchmarkIndexDailyModel.date.desc())
            .limit(1)
        )
        row = result.scalars().first()
        return row.close if row is not None else None

    async def get_close_series(self, index_code: str) -> dict[date, Decimal]:
        """Return every persisted close for ``index_code``, keyed by date."""
        result = await self._session.execute(
            select(BenchmarkIndexDailyModel.date, BenchmarkIndexDailyModel.close).where(
                BenchmarkIndexDailyModel.index_code == index_code
            )
        )
        return {row.date: row.close for row in result.all()}
