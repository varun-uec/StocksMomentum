"""List, read, create and change the caller's research records."""

from __future__ import annotations

from uuid import UUID

from wickstreet.context import TenantContext
from wickstreet.workspace.domain.records import (
    RecordDraft,
    RecordStore,
    ResearchRecord,
    UnknownRecordError,
    VersionConflictError,
    check_draft,
    check_kind,
)


class Workspace:
    """The caller's saved research, with optimistic concurrency on every change."""

    def __init__(self, store: RecordStore) -> None:
        """Create the use cases over a store."""
        self._store = store

    async def list(
        self, context: TenantContext, kind: str | None = None, archived: bool = False
    ) -> list[ResearchRecord]:
        """Return the caller's live (or archived) records, optionally of one kind."""
        return await self._store.list(context, check_kind(kind) if kind else None, archived)

    async def get(self, context: TenantContext, record_id: UUID) -> ResearchRecord:
        """Return one record, or raise :class:`UnknownRecordError`."""
        record = await self._store.get(context, record_id)
        if record is None:
            raise UnknownRecordError
        return record

    async def create(self, context: TenantContext, kind: str, draft: RecordDraft) -> ResearchRecord:
        """Save a new record."""
        return await self._store.create(context, check_kind(kind), check_draft(draft))

    async def update(
        self, context: TenantContext, record_id: UUID, expected: int, draft: RecordDraft
    ) -> ResearchRecord:
        """Replace a record the caller read at ``expected``.

        Raises :class:`VersionConflictError` when another change came first, and
        :class:`UnknownRecordError` when the record is not the caller's.
        """
        updated = await self._store.update(context, record_id, expected, check_draft(draft))
        if updated is not None:
            return updated
        current = await self.get(context, record_id)
        raise VersionConflictError(current.version)
