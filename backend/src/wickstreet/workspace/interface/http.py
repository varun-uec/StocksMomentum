"""``/workspace/records``: the caller's watchlists, screens, notes, briefs and scenarios.

A change needs ``If-Match`` with the version the client read (428 without it). A
stale version gets 412 with the current version, so the client can merge.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field

from wickstreet.dependencies import Context, TenantSession
from wickstreet.workspace.application.records import Workspace
from wickstreet.workspace.domain.records import RecordDraft, ResearchRecord
from wickstreet.workspace.infrastructure.store import SqlRecordStore

router = APIRouter(prefix="/workspace", tags=["mf-workspace"])


class RecordIn(BaseModel):
    """A record's editable parts."""

    name: str
    body: dict[str, Any] = Field(default_factory=dict)
    schema_version: int = 1
    archived: bool = False


class NewRecordIn(RecordIn):
    """A new record: its kind, then its editable parts."""

    kind: str


class RecordOut(BaseModel):
    """A saved record."""

    id: UUID
    kind: str
    name: str
    body: dict[str, Any]
    schema_version: int
    version: int
    created_at: datetime
    updated_at: datetime
    archived: bool


def _out(record: ResearchRecord, response: Response | None = None) -> RecordOut:
    if response is not None:
        response.headers["ETag"] = f'"{record.version}"'
    return RecordOut(**{name: getattr(record, name) for name in RecordOut.model_fields})


def _draft(body: RecordIn) -> RecordDraft:
    return RecordDraft(body.name, body.body, body.schema_version, body.archived)


def _expected(if_match: str | None) -> int:
    if if_match is None:
        raise HTTPException(status_code=428, detail="Send If-Match with the version you read.")
    try:
        return int(if_match.strip().removeprefix("W/").strip('"'))
    except ValueError:
        raise HTTPException(status_code=412, detail="If-Match is not a record version.") from None


@router.get("/records")
async def list_records(
    context: Context,
    session: TenantSession,
    kind: Annotated[str | None, Query()] = None,
    archived: bool = False,
) -> list[RecordOut]:
    """Return the caller's records, newest change first."""
    records = await Workspace(SqlRecordStore(session)).list(context, kind, archived)
    return [_out(record) for record in records]


@router.post("/records", status_code=201)
async def create_record(
    context: Context, session: TenantSession, body: NewRecordIn, response: Response
) -> RecordOut:
    """Save a new record at version 1."""
    record = await Workspace(SqlRecordStore(session)).create(context, body.kind, _draft(body))
    return _out(record, response)


@router.get("/records/{record_id}")
async def get_record(
    context: Context, session: TenantSession, record_id: UUID, response: Response
) -> RecordOut:
    """Return one record and its version as the ETag."""
    return _out(await Workspace(SqlRecordStore(session)).get(context, record_id), response)


@router.put("/records/{record_id}")
async def replace_record(
    context: Context,
    session: TenantSession,
    record_id: UUID,
    body: RecordIn,
    response: Response,
    if_match: Annotated[str | None, Header()] = None,
) -> RecordOut:
    """Replace a record the caller read at the If-Match version."""
    workspace = Workspace(SqlRecordStore(session))
    record = await workspace.update(context, record_id, _expected(if_match), _draft(body))
    return _out(record, response)
