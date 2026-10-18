"""Alert repository: daily alerts on chart series values (FR-22, M15)."""

from __future__ import annotations

from datetime import date
from typing import cast

from sqlalchemy import Select, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.entities.alert import (
    Alert,
    AlertCondition,
    AlertInterval,
    AlertSource,
    AlertStatus,
    Firing,
)
from momentum25.infrastructure.persistence.models import AlertModel, SecurityModel


def _to_entity(row: AlertModel, symbol: str) -> Alert:
    # Only this repository writes these columns, always with the literal types.
    return Alert(
        id=row.id,
        symbol=symbol,
        source=cast(AlertSource, row.source),
        interval=cast(AlertInterval, row.interval),
        condition=cast(AlertCondition, row.condition),
        threshold=row.threshold,
        armed_after=row.armed_after,
        status=cast(AlertStatus, row.status),
        triggered_on=row.triggered_on,
        trigger_value=row.trigger_value,
        data_version=row.data_version,
        seen=row.seen,
        created_at=row.created_at,
    )


def _with_symbol() -> Select[tuple[AlertModel, str]]:
    return select(AlertModel, SecurityModel.symbol).join(
        SecurityModel, SecurityModel.id == AlertModel.security_id
    )


class SqlAlertRepository:
    """Async SQLAlchemy implementation of :class:`AlertRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind the repository to a unit-of-work session."""
        self._session = session

    async def list_all(self) -> list[Alert]:
        """Return every alert: fired ones first, newest firing first, then active ones."""
        result = await self._session.execute(
            _with_symbol().order_by(
                AlertModel.triggered_on.desc().nulls_last(), AlertModel.id.desc()
            )
        )
        return [_to_entity(row, symbol) for row, symbol in result.all()]

    async def list_active(self) -> list[Alert]:
        """Return the alerts still watching, oldest first."""
        result = await self._session.execute(
            _with_symbol().where(AlertModel.status == "active").order_by(AlertModel.id)
        )
        return [_to_entity(row, symbol) for row, symbol in result.all()]

    async def add(self, security_id: int, alert: Alert) -> Alert:
        """Store a new active alert and return it with its id."""
        row = AlertModel(
            security_id=security_id,
            source=alert.source,
            interval=alert.interval,
            condition=alert.condition,
            threshold=alert.threshold,
            armed_after=alert.armed_after,
        )
        self._session.add(row)
        await self._session.commit()
        await self._session.refresh(row)
        return _to_entity(row, alert.symbol)

    async def delete(self, alert_id: int) -> bool:
        """Delete an alert; return False if it did not exist."""
        result = await self._session.execute(delete(AlertModel).where(AlertModel.id == alert_id))
        await self._session.commit()
        return bool(result.rowcount)  # type: ignore[attr-defined]

    async def fire(self, alert_id: int, firing: Firing, data_version: str) -> None:
        """Record the firing bar; the status condition makes a second firing a no-op."""
        await self._session.execute(
            update(AlertModel)
            .where(AlertModel.id == alert_id, AlertModel.status == "active")
            .values(
                status="triggered",
                triggered_on=firing.date,
                trigger_value=firing.value,
                data_version=data_version,
                seen=False,
            )
        )
        await self._session.commit()

    async def rearm(self, alert_id: int, armed_after: date) -> Alert | None:
        """Make the alert watch again from bars after ``armed_after``."""
        await self._session.execute(
            update(AlertModel)
            .where(AlertModel.id == alert_id)
            .values(
                status="active",
                armed_after=armed_after,
                triggered_on=None,
                trigger_value=None,
                data_version=None,
                seen=False,
            )
        )
        await self._session.commit()
        result = await self._session.execute(_with_symbol().where(AlertModel.id == alert_id))
        found = result.first()
        return _to_entity(found[0], found[1]) if found else None

    async def mark_seen(self) -> int:
        """Mark every fired alert seen; return how many changed."""
        result = await self._session.execute(
            update(AlertModel)
            .where(AlertModel.status == "triggered", AlertModel.seen.is_(False))
            .values(seen=True)
        )
        await self._session.commit()
        return int(result.rowcount)  # type: ignore[attr-defined]
