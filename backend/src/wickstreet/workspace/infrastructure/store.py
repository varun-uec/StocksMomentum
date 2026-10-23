"""PostgreSQL record store.

Each query names the caller's tenant and owner, and row-level security applies the
tenant rule again (ADR-023 §2.6). The version check and the write are one UPDATE,
so two concurrent saves cannot both pass it.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from wickstreet.context import TenantContext
from wickstreet.workspace.domain.records import RecordDraft, RecordKind, ResearchRecord
from wickstreet.workspace.infrastructure.tables import research_record as t

_COLUMNS = (
    t.c.id,
    t.c.kind,
    t.c.name,
    t.c.body,
    t.c.schema_version,
    t.c.version,
    t.c.created_at,
    t.c.updated_at,
    t.c.archived,
)


def _record(row: Sequence[Any]) -> ResearchRecord:
    return ResearchRecord(*row)


def _mine(context: TenantContext) -> tuple[Any, ...]:
    return (t.c.tenant_id == context.tenant_id, t.c.owner_id == context.user_id)


class SqlRecordStore:
    """Record store over a tenant-scoped session (``tenant_transaction``)."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind the store to the unit of work's session."""
        self._session = session

    async def list(
        self, context: TenantContext, kind: RecordKind | None, archived: bool
    ) -> list[ResearchRecord]:
        """Return the owner's records, newest change first, then by name."""
        query = select(*_COLUMNS).where(*_mine(context), t.c.archived == archived)
        if kind is not None:
            query = query.where(t.c.kind == kind)
        rows = await self._session.execute(query.order_by(t.c.updated_at.desc(), t.c.name, t.c.id))
        return [_record(row) for row in rows]

    async def get(self, context: TenantContext, record_id: UUID) -> ResearchRecord | None:
        """Return one of the owner's records, or None."""
        row = (
            await self._session.execute(
                select(*_COLUMNS).where(*_mine(context), t.c.id == record_id)
            )
        ).first()
        return _record(row) if row else None

    async def create(
        self, context: TenantContext, kind: RecordKind, draft: RecordDraft
    ) -> ResearchRecord:
        """Insert a record at version 1."""
        row = (
            await self._session.execute(
                insert(t)
                .values(
                    id=uuid4(),
                    tenant_id=context.tenant_id,
                    owner_id=context.user_id,
                    kind=kind,
                    name=draft.name,
                    body=draft.body,
                    schema_version=draft.schema_version,
                    version=1,
                    archived=draft.archived,
                )
                .returning(*_COLUMNS)
            )
        ).one()
        return _record(row)

    async def update(
        self, context: TenantContext, record_id: UUID, expected: int, draft: RecordDraft
    ) -> ResearchRecord | None:
        """Replace the record if it is at ``expected``; None when it is not."""
        row = (
            await self._session.execute(
                update(t)
                .where(*_mine(context), t.c.id == record_id, t.c.version == expected)
                .values(
                    name=draft.name,
                    body=draft.body,
                    schema_version=draft.schema_version,
                    archived=draft.archived,
                    version=t.c.version + 1,
                    updated_at=func.now(),
                )
                .returning(*_COLUMNS)
            )
        ).first()
        return _record(row) if row else None
