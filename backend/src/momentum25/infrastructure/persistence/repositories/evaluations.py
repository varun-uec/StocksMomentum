"""Evaluation repository: the Strategy Studio's research namespace (ADR-014 §5–7)."""

from __future__ import annotations

from datetime import date
from typing import Any, cast

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.entities.evaluation import Evaluation, EvaluationStatus
from momentum25.domain.errors import ConflictError
from momentum25.domain.research.strategy_evaluation import ResultClass
from momentum25.infrastructure.persistence.models import StrategyEvaluationModel

_Row = StrategyEvaluationModel


def _entity(row: _Row) -> Evaluation:
    # Only this repository writes these columns, always with the literal types.
    return Evaluation(
        id=row.id,
        family_id=row.family_id,
        config_hash=row.config_hash,
        result_class=cast(ResultClass, row.result_class),
        window_start=row.window_start,
        window_end=row.window_end,
        data_version=row.data_version,
        status=cast(EvaluationStatus, row.status),
        progress_done=row.progress_done,
        progress_total=row.progress_total,
        result=row.result,
        error=row.error,
        created_at=row.created_at,
        completed_at=row.completed_at,
    )


class SqlEvaluationRepository:
    """Async SQLAlchemy implementation of :class:`EvaluationRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind the repository to a unit-of-work session."""
        self._session = session

    async def create(
        self,
        family_id: int,
        config_hash: str,
        result_class: ResultClass,
        window: tuple[date, date],
        data_version: str,
    ) -> Evaluation:
        """Queue an evaluation.

        Raise ``ConflictError`` if the family's hold-out is spent, or if the same
        In-Sample run is already stored.
        """
        row = _Row(
            family_id=family_id,
            config_hash=config_hash,
            result_class=result_class,
            window_start=window[0],
            window_end=window[1],
            data_version=data_version,
        )
        try:
            async with self._session.begin_nested():
                self._session.add(row)
        except IntegrityError as exc:
            if result_class == "in_sample":
                raise ConflictError(
                    f"Family {family_id} already has this In-Sample run on "
                    f"{window[0]}..{window[1]}"
                ) from exc
            raise ConflictError(
                f"Family {family_id} has spent its hold-out on {window[0]}..{window[1]}: "
                "one Out-of-Sample Evaluation per family per window"
            ) from exc
        await self._session.commit()
        await self._session.refresh(row)
        return _entity(row)

    async def get(self, evaluation_id: int) -> Evaluation | None:
        """Return an evaluation, or ``None``."""
        row = await self._session.get(_Row, evaluation_id, populate_existing=True)
        return None if row is None else _entity(row)

    async def list_for_family(self, family_id: int) -> list[Evaluation]:
        """Return a family's evaluations, newest first."""
        rows = await self._session.scalars(
            select(_Row).where(_Row.family_id == family_id).order_by(_Row.id.desc())
        )
        return [_entity(row) for row in rows]

    async def _set(self, evaluation_id: int, **values: Any) -> None:
        await self._session.execute(update(_Row).where(_Row.id == evaluation_id).values(**values))
        await self._session.commit()

    async def start(self, evaluation_id: int, total: int) -> None:
        """Mark an evaluation running with ``total`` steps."""
        await self._set(
            evaluation_id, status="running", progress_done=0, progress_total=total, error=None
        )

    async def advance(self, evaluation_id: int, done: int) -> None:
        """Record how many steps are done."""
        await self._set(evaluation_id, progress_done=done)

    async def complete(self, evaluation_id: int, result: dict[str, Any]) -> None:
        """Store the result; the row is final afterwards."""
        await self._set(evaluation_id, status="completed", result=result, completed_at=func.now())

    async def rebase(self, evaluation_id: int, data_version: str) -> None:
        """Point an unfinished evaluation at a manifest with today's code state."""
        await self._set(evaluation_id, data_version=data_version)

    async def fail(self, evaluation_id: int, error: str) -> None:
        """Mark an evaluation failed."""
        await self._set(evaluation_id, status="failed", error=error)

    async def requeue(self, evaluation_id: int) -> bool:
        """Queue a failed evaluation again; False if it was not failed."""
        result = await self._session.execute(
            update(_Row)
            .where(_Row.id == evaluation_id, _Row.status == "failed")
            .values(status="queued", progress_done=0, error=None)
        )
        await self._session.commit()
        return bool(result.rowcount)  # type: ignore[attr-defined]

    async def families_on_window(self, window: tuple[date, date], up_to_id: int) -> int:
        """Families that submitted an Out-of-Sample Evaluation on ``window`` by ``up_to_id``."""
        count = await self._session.scalar(
            select(func.count(func.distinct(_Row.family_id))).where(
                _Row.result_class == "out_of_sample",
                _Row.window_start == window[0],
                _Row.window_end == window[1],
                _Row.id <= up_to_id,
            )
        )
        return int(count or 0)

    async def find_in_sample(
        self, family_id: int, config_hash: str, window: tuple[date, date], data_version: str
    ) -> Evaluation | None:
        """The In-Sample evaluation with this run identity, or ``None``."""
        row = await self._session.scalar(
            select(_Row)
            .where(
                _Row.family_id == family_id,
                _Row.config_hash == config_hash,
                _Row.result_class == "in_sample",
                _Row.window_start == window[0],
                _Row.window_end == window[1],
                _Row.data_version == data_version,
            )
            .order_by(_Row.id)
            .limit(1)
        )
        return None if row is None else _entity(row)

    async def research_runs(self, family_id: int) -> int:
        """Distinct Historical Research — In-Sample run identities in a family.

        A run is one config on one window at one data version. A retry reuses
        its row, and a repeated submit finds it, so neither counts twice.
        """
        identities = (
            select(_Row.config_hash, _Row.window_start, _Row.window_end, _Row.data_version)
            .where(_Row.family_id == family_id, _Row.result_class == "in_sample")
            .distinct()
            .subquery()
        )
        return int(await self._session.scalar(select(func.count()).select_from(identities)) or 0)

    async def interrupt_unfinished(self) -> int:
        """Fail every queued or running evaluation (after a restart)."""
        result = await self._session.execute(
            update(_Row)
            .where(_Row.status.in_(("queued", "running")))
            .values(status="failed", error="Interrupted by a restart. Retry to run it again.")
        )
        await self._session.commit()
        return int(result.rowcount)  # type: ignore[attr-defined]
