"""Async SQLAlchemy engine, session factory, and lifecycle management.

Provides connection pooling, a unit-of-work session context manager (transaction
management), and a disposable lifecycle for graceful shutdown.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from momentum25.infrastructure.config.settings import Settings, get_settings


class Database:
    """Owns the async engine and session factory for the application."""

    def __init__(self, settings: Settings) -> None:
        """Create the async engine and session factory from settings."""
        self._engine: AsyncEngine = create_async_engine(
            settings.database_url,
            echo=settings.db_echo,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_pre_ping=True,
        )
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            expire_on_commit=False,
            autoflush=False,
        )

    @property
    def engine(self) -> AsyncEngine:
        """Return the underlying async engine."""
        return self._engine

    def new_session(self) -> AsyncSession:
        """Return a new ``AsyncSession``; the caller owns its lifecycle.

        Used by the FastAPI dependency layer, which wires repositories with a live
        session rather than the unit-of-work context manager.
        """
        return self._session_factory()

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Yield a session wrapped in a transaction (commit on success, rollback on error).

        This is the unit-of-work boundary used by repositories and use cases.
        """
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def dispose(self) -> None:
        """Dispose of the engine and its connection pool (graceful shutdown)."""
        await self._engine.dispose()


@lru_cache(maxsize=1)
def get_database() -> Database:
    """Return the cached :class:`Database` singleton."""
    return Database(get_settings())
