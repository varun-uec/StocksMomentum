"""Strategy repository — persistence for versioned strategy definitions."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.entities.strategy import Strategy
from momentum25.infrastructure.config.strategy_loader import config_from_raw, raw_from_config
from momentum25.infrastructure.persistence.models import StrategyModel


def _to_domain(row: StrategyModel) -> Strategy:
    """Map an ORM row to a domain :class:`Strategy`."""
    return Strategy(
        id=row.id,
        name=row.name,
        version=row.version,
        is_active=row.is_active,
        config=config_from_raw(row.config),
        config_hash=row.config_hash,
    )


class SqlStrategyRepository:
    """Async SQLAlchemy implementation of :class:`StrategyRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind the repository to a unit-of-work session."""
        self._session = session

    async def upsert(self, strategy: Strategy) -> int:
        """Insert or update a strategy by (name, version); return its id."""
        stmt = insert(StrategyModel).values(
            name=strategy.name,
            version=strategy.version,
            is_active=strategy.is_active,
            config=raw_from_config(strategy.config),
            config_hash=strategy.config_hash,
        )
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=[StrategyModel.name, StrategyModel.version],
            set_={
                "is_active": stmt.excluded.is_active,
                "config": stmt.excluded.config,
                "config_hash": stmt.excluded.config_hash,
            },
        ).returning(StrategyModel.id)
        result = await self._session.execute(upsert_stmt)
        return int(result.scalar_one())

    async def get_active(self, name: str) -> Strategy | None:
        """Return the active strategy with the given name, or ``None``."""
        result = await self._session.execute(
            select(StrategyModel)
            .where(StrategyModel.name == name, StrategyModel.is_active.is_(True))
            .order_by(StrategyModel.version.desc())
        )
        row = result.scalars().first()
        return _to_domain(row) if row else None

    async def list(self) -> list[Strategy]:
        """Return all strategies."""
        result = await self._session.execute(select(StrategyModel).order_by(StrategyModel.name))
        return [_to_domain(row) for row in result.scalars().all()]
