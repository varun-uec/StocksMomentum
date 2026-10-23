"""Research records: watchlists, saved screens, notes, briefs and scenarios (W1).

The body is the client's versioned document; the server checks only its kind,
name and size. Every change names the version it read, so a second window can
never overwrite edits it has not seen.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol, get_args
from uuid import UUID

from wickstreet.context import TenantContext

RecordKind = Literal["watchlist", "screen", "note", "brief", "scenario"]
KINDS: frozenset[str] = frozenset(get_args(RecordKind))
MAX_NAME = 120
# Serialised JSON bytes; a watchlist of 500 codes is about 6 KB.
MAX_BODY = 256 * 1024


class InvalidRecordError(ValueError):
    """The kind, name or body breaks a record rule."""


class UnknownRecordError(LookupError):
    """No record with that id belongs to the caller."""


class VersionConflictError(Exception):
    """The record changed after the caller read it."""

    def __init__(self, current: int) -> None:
        """Remember the version the store holds now."""
        super().__init__(f"The record is at version {current}.")
        self.current = current


@dataclass(frozen=True, slots=True)
class ResearchRecord:
    """One saved record; ``version`` starts at 1 and grows by one per change."""

    id: UUID
    kind: RecordKind
    name: str
    body: dict[str, Any]
    schema_version: int
    version: int
    created_at: datetime
    updated_at: datetime
    archived: bool


@dataclass(frozen=True, slots=True)
class RecordDraft:
    """What a caller may set on a record."""

    name: str
    body: dict[str, Any]
    schema_version: int = 1
    archived: bool = False


def check_kind(kind: str) -> RecordKind:
    """Return ``kind`` as a record kind, or raise :class:`InvalidRecordError`."""
    if kind not in KINDS:
        raise InvalidRecordError(f"Unknown record kind {kind!r}.")
    return kind  # type: ignore[return-value]


def check_draft(draft: RecordDraft) -> RecordDraft:
    """Return the draft with its name trimmed, or raise :class:`InvalidRecordError`."""
    name = draft.name.strip()
    if not 1 <= len(name) <= MAX_NAME:
        raise InvalidRecordError(f"A name has 1 to {MAX_NAME} characters.")
    if draft.schema_version < 1:
        raise InvalidRecordError("schema_version starts at 1.")
    if len(json.dumps(draft.body, separators=(",", ":")).encode()) > MAX_BODY:
        raise InvalidRecordError(f"A record body holds at most {MAX_BODY // 1024} KB.")
    return RecordDraft(name, draft.body, draft.schema_version, draft.archived)


class RecordStore(Protocol):
    """Port for the caller's records. Every method acts inside the caller's tenant."""

    async def list(
        self, context: TenantContext, kind: RecordKind | None, archived: bool
    ) -> list[ResearchRecord]:
        """Return the owner's records, newest change first."""
        ...

    async def get(self, context: TenantContext, record_id: UUID) -> ResearchRecord | None:
        """Return one of the owner's records, or None."""
        ...

    async def create(
        self, context: TenantContext, kind: RecordKind, draft: RecordDraft
    ) -> ResearchRecord:
        """Insert a record at version 1."""
        ...

    async def update(
        self, context: TenantContext, record_id: UUID, expected: int, draft: RecordDraft
    ) -> ResearchRecord | None:
        """Replace the record if it is at ``expected``; None when it is not."""
        ...
