"""Watchlist repository — persistence for the single global tracked-symbol list."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.infrastructure.persistence.models import SecurityModel, WatchlistItemModel


class SqlWatchlistRepository:
    """Async SQLAlchemy implementation of :class:`WatchlistRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind the repository to a unit-of-work session."""
        self._session = session

    async def add(self, security_id: int) -> None:
        """Add a security to the watchlist, idempotently.

        ``ON CONFLICT DO NOTHING`` rather than a read-then-write: starring an
        already-starred symbol must not raise, and must not create a duplicate.
        """
        stmt = (
            insert(WatchlistItemModel)
            .values(security_id=security_id)
            .on_conflict_do_nothing(index_elements=[WatchlistItemModel.security_id])
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def remove(self, security_id: int) -> None:
        """Remove a security from the watchlist; absent is not an error."""
        await self._session.execute(
            delete(WatchlistItemModel).where(WatchlistItemModel.security_id == security_id)
        )
        await self._session.commit()

    async def list_symbols(self) -> list[str]:
        """Return the watchlisted symbols, oldest addition first."""
        result = await self._session.execute(
            select(SecurityModel.symbol)
            .join(WatchlistItemModel, WatchlistItemModel.security_id == SecurityModel.id)
            .order_by(WatchlistItemModel.added_at, WatchlistItemModel.id)
        )
        return list(result.scalars().all())
