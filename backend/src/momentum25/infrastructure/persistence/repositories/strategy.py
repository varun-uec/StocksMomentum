"""Strategy repository — persistence for versioned strategy definitions."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.entities.strategy import Strategy
from momentum25.domain.value_objects.types import RunStatus
from momentum25.infrastructure.config.strategy_loader import config_from_raw, raw_from_config
from momentum25.infrastructure.persistence.models import ScreeningRunModel, StrategyModel

_BuiltinList = list


def _to_domain(row: StrategyModel) -> Strategy:
    """Map an ORM row to a domain :class:`Strategy`."""
    return Strategy(
        id=row.id,
        name=row.name,
        version=row.version,
        is_active=row.is_active,
        kind=row.kind,
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
            kind=strategy.kind,
            config=raw_from_config(strategy.config),
            config_hash=strategy.config_hash,
        )
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=[StrategyModel.name, StrategyModel.version],
            set_={
                "is_active": stmt.excluded.is_active,
                "kind": stmt.excluded.kind,
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

    async def list_with_completed_runs(self) -> _BuiltinList[Strategy]:
        """Return strategies that have at least one completed live run.

        Excludes historical backfill and research/walk-forward runs, mirroring
        :meth:`SqlScreeningRunRepository.latest_completed` -- the same set the
        Live Dashboard resolves "latest run" against. Used to build a strategy
        selector that can never present an option with nothing to show.
        """
        result = await self._session.execute(
            select(StrategyModel)
            .join(ScreeningRunModel, ScreeningRunModel.strategy_id == StrategyModel.id)
            .where(
                StrategyModel.kind == "production",
                ScreeningRunModel.status == RunStatus.COMPLETED.value,
                ~ScreeningRunModel.data_version.like("historical:%"),
                ~ScreeningRunModel.data_version.like("%:research:%"),
                ~ScreeningRunModel.data_version.like("%:icv2:%"),
            )
            .distinct()
            .order_by(StrategyModel.name)
        )
        return [_to_domain(row) for row in result.scalars().all()]

    async def delete_orphans(self, names_on_disk: _BuiltinList[str]) -> _BuiltinList[str]:
        """Delete strategies not present on disk, but only those with no runs.

        Disk is the permanent source of truth for strategy definitions; removing
        a JSON file must eventually remove the row. Run history is append-only
        (ADR-006), so a strategy with stored runs is left alone.
        """
        result = await self._session.execute(
            select(StrategyModel)
            .outerjoin(ScreeningRunModel, ScreeningRunModel.strategy_id == StrategyModel.id)
            .where(
                ~StrategyModel.name.in_(names_on_disk),
                ScreeningRunModel.id.is_(None),
            )
        )
        orphans = list(result.scalars().all())
        if orphans:
            for row in orphans:
                await self._session.delete(row)
            # The caller re-lists strategies (to find run-bearing orphans) in the
            # same transaction; pending deletes would otherwise still be visible
            # to that SELECT.
            await self._session.flush()
        return [row.name for row in orphans]
