"""Strategy repository — persistence for versioned strategy definitions."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from momentum25.domain.entities.strategy import Strategy
from momentum25.domain.errors import ConflictError
from momentum25.domain.strategy.config_codec import raw_from_config
from momentum25.domain.value_objects.types import RunStatus
from momentum25.infrastructure.config.strategy_loader import config_from_raw
from momentum25.infrastructure.persistence.models import ScreeningRunModel, StrategyModel

_BuiltinList = list


def strategy_from_row(row: StrategyModel) -> Strategy:
    """Map an ORM row to a domain :class:`Strategy`."""
    return Strategy(
        id=row.id,
        name=row.name,
        version=row.version,
        is_active=row.is_active,
        kind=row.kind,
        config=config_from_raw(row.config),
        config_hash=row.config_hash,
        family_id=row.family_id,
        parent_config_hash=row.parent_config_hash,
    )


# Generic strategy reads remain production-only. Saved versions enter the
# workstation only through the explicit workspace methods below.
_NOT_USER = StrategyModel.kind != "user"


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
            where=_NOT_USER,
        ).returning(StrategyModel.id)
        strategy_id = (await self._session.execute(upsert_stmt)).scalar_one_or_none()
        if strategy_id is None:
            raise ConflictError(
                f"Strategy {strategy.name!r} v{strategy.version} is a user strategy; "
                "a strategy file cannot replace it"
            )
        return int(strategy_id)

    async def get_active(self, name: str) -> Strategy | None:
        """Return an active strategy-file definition; user configs stay excluded."""
        result = await self._session.execute(
            select(StrategyModel)
            .where(StrategyModel.name == name, StrategyModel.is_active.is_(True), _NOT_USER)
            .order_by(StrategyModel.version.desc())
        )
        row = result.scalars().first()
        return strategy_from_row(row) if row else None

    async def get_for_workspace(
        self, name: str, config_hash: str | None = None
    ) -> Strategy | None:
        """Resolve the selected strategy version for screening and chart context."""
        query = select(StrategyModel).where(
            StrategyModel.name == name,
            StrategyModel.is_active.is_(True),
            StrategyModel.kind.in_(("production", "user")),
        )
        if config_hash is not None:
            query = query.where(StrategyModel.config_hash == config_hash)
        else:
            newest = (
                select(StrategyModel.version)
                .where(
                    StrategyModel.name == name,
                    StrategyModel.is_active.is_(True),
                    StrategyModel.kind.in_(("production", "user")),
                )
                .order_by(StrategyModel.version.desc(), StrategyModel.id.desc())
                .limit(1)
                .scalar_subquery()
            )
            query = query.where(StrategyModel.version == newest)
        row = (await self._session.execute(query)).scalars().first()
        return strategy_from_row(row) if row else None

    async def get_by_id(self, strategy_id: int) -> Strategy | None:
        """Load the exact definition pinned by a screening run."""
        row = await self._session.get(StrategyModel, strategy_id)
        return strategy_from_row(row) if row else None

    async def list_all(self) -> list[Strategy]:
        """List every persisted strategy version for run provenance resolution."""
        rows = await self._session.scalars(
            select(StrategyModel).order_by(StrategyModel.name, StrategyModel.version)
        )
        return [strategy_from_row(row) for row in rows]

    async def list_for_workspace(
        self, include_users: bool = False, with_runs: bool = False
    ) -> list[Strategy]:
        """List current built-ins and, when requested, all saved user versions."""
        from sqlalchemy import or_

        query = select(StrategyModel).where(StrategyModel.is_active.is_(True))
        builtin = aliased(StrategyModel)
        latest_builtin = (
            select(builtin.version)
            .where(
                builtin.name == StrategyModel.name,
                builtin.kind == "production",
                builtin.is_active.is_(True),
            )
            .order_by(builtin.version.desc(), builtin.id.desc())
            .limit(1)
            .scalar_subquery()
        )
        if include_users:
            query = query.where(
                or_(
                    StrategyModel.kind == "user",
                    (StrategyModel.kind == "production")
                    & (StrategyModel.version == latest_builtin),
                )
            )
        else:
            query = query.where(
                (StrategyModel.kind == "production") & (StrategyModel.version == latest_builtin)
            )
        if with_runs:
            query = query.join(ScreeningRunModel, ScreeningRunModel.strategy_id == StrategyModel.id)
            query = query.where(
                ScreeningRunModel.status == RunStatus.COMPLETED.value,
                ~ScreeningRunModel.data_version.like("historical:%"),
                ~ScreeningRunModel.data_version.like("%:research:%"),
                ~ScreeningRunModel.data_version.like("%:icv2:%"),
            ).distinct()
        rows = await self._session.scalars(query.order_by(StrategyModel.name))
        return [strategy_from_row(row) for row in rows]

    async def list(self) -> list[Strategy]:
        """Return all strategies except user strategies."""
        result = await self._session.execute(
            select(StrategyModel).where(_NOT_USER).order_by(StrategyModel.name)
        )
        return [strategy_from_row(row) for row in result.scalars().all()]

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
        return [strategy_from_row(row) for row in result.scalars().all()]

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
                _NOT_USER,
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
