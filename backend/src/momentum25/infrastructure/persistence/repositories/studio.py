"""Strategy Studio repository: families and user strategies (ADR-014 §3–4)."""

from __future__ import annotations

from dataclasses import replace

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.entities.strategy import Strategy, StrategyFamily
from momentum25.domain.errors import ConflictError
from momentum25.domain.strategy.config_codec import raw_from_config
from momentum25.infrastructure.persistence.models import StrategyFamilyModel, StrategyModel
from momentum25.infrastructure.persistence.repositories.strategy import strategy_from_row


def _family(row: StrategyFamilyModel) -> StrategyFamily:
    return StrategyFamily(
        id=row.id,
        hypothesis=row.hypothesis,
        root_config_hash=row.root_config_hash,
        created_at=row.created_at,
    )


class SqlStudioRepository:
    """Async SQLAlchemy implementation of :class:`StudioRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind the repository to a unit-of-work session."""
        self._session = session

    async def create_family(
        self, hypothesis: str, hypothesis_key: str, root_config_hash: str, first: Strategy
    ) -> StrategyFamily:
        """Store a family and its first member together.

        Refuses a hypothesis another family already states.
        """
        row = StrategyFamilyModel(
            hypothesis=hypothesis, hypothesis_key=hypothesis_key, root_config_hash=root_config_hash
        )
        try:
            async with self._session.begin_nested():
                self._session.add(row)
        except IntegrityError as exc:
            raise ConflictError("Another family already states this hypothesis") from exc
        await self._insert(replace(first, family_id=row.id))
        await self._session.commit()
        await self._session.refresh(row)
        return _family(row)

    async def get_family(self, family_id: int) -> StrategyFamily | None:
        """Return a family, or ``None``."""
        row = await self._session.get(StrategyFamilyModel, family_id)
        return None if row is None else _family(row)

    async def list_families(self) -> list[StrategyFamily]:
        """Return every family, oldest first."""
        rows = await self._session.scalars(
            select(StrategyFamilyModel).order_by(StrategyFamilyModel.id)
        )
        return [_family(row) for row in rows]

    async def add_strategy(self, strategy: Strategy) -> Strategy:
        """Store a new user strategy; rows are never updated afterwards."""
        row = await self._insert(strategy)
        await self._session.commit()
        return strategy_from_row(row)

    async def _insert(self, strategy: Strategy) -> StrategyModel:
        row = StrategyModel(
            name=strategy.name,
            version=strategy.version,
            is_active=True,
            kind="user",
            config=raw_from_config(strategy.config),
            config_hash=strategy.config_hash,
            family_id=strategy.family_id,
            parent_config_hash=strategy.parent_config_hash,
        )
        try:
            async with self._session.begin_nested():
                self._session.add(row)
        except IntegrityError as exc:
            raise ConflictError(f"{strategy.name!r} v{strategy.version} already exists") from exc
        return row

    async def get_strategy(self, config_hash: str) -> Strategy | None:
        """Return the user strategy with this hash, or ``None``."""
        row = await self._session.scalar(
            select(StrategyModel).where(
                StrategyModel.kind == "user", StrategyModel.config_hash == config_hash
            )
        )
        return None if row is None else strategy_from_row(row)

    async def get_builtin(self, config_hash: str) -> Strategy | None:
        """Return the strategy file (not a user strategy) with this hash, or ``None``."""
        row = await self._session.scalar(
            select(StrategyModel)
            .where(StrategyModel.kind != "user", StrategyModel.config_hash == config_hash)
            .order_by(StrategyModel.id)
        )
        return None if row is None else strategy_from_row(row)

    async def members(self, family_id: int) -> list[Strategy]:
        """Return a family's strategies in the order they were saved."""
        rows = await self._session.scalars(
            select(StrategyModel)
            .where(StrategyModel.family_id == family_id)
            .order_by(StrategyModel.id)
        )
        return [strategy_from_row(row) for row in rows]

    async def named(self, name: str) -> Strategy | None:
        """Return any stored strategy called ``name`` (file or user), or ``None``."""
        row = await self._session.scalar(
            select(StrategyModel).where(StrategyModel.name == name).limit(1)
        )
        return None if row is None else strategy_from_row(row)

    async def next_version(self, name: str) -> int:
        """One more than the highest stored version of ``name``."""
        highest = await self._session.scalar(
            select(func.max(StrategyModel.version)).where(StrategyModel.name == name)
        )
        return (highest or 0) + 1
