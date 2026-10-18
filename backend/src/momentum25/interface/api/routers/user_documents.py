"""Saved workspace and drawings, with HTTP preconditions (ADR-013 §5).

| Request                                   | Response                                   |
|-------------------------------------------|--------------------------------------------|
| GET                                       | 200 + ``ETag: "<revision>"``, or 404        |
| PUT + ``If-Match`` that matches           | 200, revision + 1, new ``ETag``             |
| PUT + stale ``If-Match``                  | 412; the body holds the current document    |
| PUT with neither precondition             | 428                                         |
| PUT + ``If-None-Match: *``                | 201, or 412 if the document already exists  |
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Path, Request, Response
from fastapi.responses import JSONResponse

from momentum25.application.dto.user_documents import (
    ID_PATTERN,
    SYMBOL_PATTERN,
    SymbolDrawingsDocument,
    SymbolDrawingsV1,
    WorkspaceDocument,
    WorkspaceV1,
)
from momentum25.application.use_cases.user_documents import GetUserDocument, SaveUserDocument
from momentum25.domain.entities.user_document import DocumentKind, UserDocument
from momentum25.domain.errors import RevisionMismatchError
from momentum25.interface.api.dependencies import get_get_user_document, get_save_user_document

router = APIRouter(tags=["workspace"])

_PRECONDITION_RESPONSES: dict[int | str, dict[str, Any]] = {
    412: {"description": "The document changed since the revision you named. Body: `current`."},
    428: {"description": "Send If-Match or If-None-Match: *."},
}

WorkspaceId = Annotated[str, Path(pattern=ID_PATTERN)]
SymbolKey = Annotated[str, Path(pattern=SYMBOL_PATTERN)]
GetDep = Annotated[GetUserDocument, Depends(get_get_user_document)]
SaveDep = Annotated[SaveUserDocument, Depends(get_save_user_document)]
IfMatch = Annotated[str | None, Header()]
IfNoneMatch = Annotated[str | None, Header()]


def _etag(revision: int) -> str:
    return f'"{revision}"'


def _parse_if_match(value: str | None) -> int | None:
    """Return the revision an ``If-Match`` names. A malformed value can never match."""
    if value is None:
        return None
    tag = value.strip().removeprefix("W/").strip('"')
    return int(tag) if tag.isdigit() else 0


Presenter = type[WorkspaceDocument] | type[SymbolDrawingsDocument]


async def _read(
    kind: DocumentKind, key: str, response: Response, read: GetUserDocument, present: Presenter
) -> WorkspaceDocument | SymbolDrawingsDocument:
    document = await read.execute(kind, key)
    response.headers["ETag"] = _etag(document.revision)
    return present.of(document)


async def _save(
    kind: DocumentKind,
    key: str,
    body: dict[str, Any],
    request: Request,
    response: Response,
    if_match: str | None,
    if_none_match: str | None,
    save: SaveUserDocument,
    read: GetUserDocument,
    present: Presenter,
) -> WorkspaceDocument | SymbolDrawingsDocument | JSONResponse:
    create_only = if_none_match is not None and if_none_match.strip() == "*"
    try:
        document: UserDocument = await save.execute(
            kind,
            key,
            body,
            expected_revision=_parse_if_match(if_match),
            create_only=create_only,
        )
    except RevisionMismatchError as exc:
        return await _mismatch(kind, key, str(exc), request, read, present)
    response.status_code = 201 if create_only else 200
    response.headers["ETag"] = _etag(document.revision)
    return present.of(document)


async def _mismatch(
    kind: DocumentKind,
    key: str,
    detail: str,
    request: Request,
    read: GetUserDocument,
    present: Presenter,
) -> JSONResponse:
    """412 with the current document, so the client can recover without another request."""
    current = await read.find(kind, key)
    return JSONResponse(
        status_code=412,
        media_type="application/problem+json",
        headers={"ETag": _etag(current.revision)} if current else {},
        content={
            "type": "urn:momentum25:error:revision_mismatch",
            "title": "revision_mismatch",
            "status": 412,
            "detail": detail,
            "instance": request.url.path,
            "current": present.of(current).model_dump(mode="json") if current else None,
        },
    )


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceDocument)
async def read_workspace(workspace_id: WorkspaceId, response: Response, read: GetDep) -> Any:
    """Return the saved workspace and its revision (``ETag``)."""
    return await _read("workspace", workspace_id, response, read, WorkspaceDocument)


@router.put(
    "/workspaces/{workspace_id}",
    response_model=WorkspaceDocument,
    responses=_PRECONDITION_RESPONSES,
)
async def save_workspace(
    workspace_id: WorkspaceId,
    body: WorkspaceV1,
    request: Request,
    response: Response,
    save: SaveDep,
    read: GetDep,
    if_match: IfMatch = None,
    if_none_match: IfNoneMatch = None,
) -> Any:
    """Save the workspace if it is still at the revision named in ``If-Match``."""
    return await _save(
        "workspace",
        workspace_id,
        body.model_dump(mode="json"),
        request,
        response,
        if_match,
        if_none_match,
        save,
        read,
        WorkspaceDocument,
    )


@router.get("/drawings/{symbol}", response_model=SymbolDrawingsDocument)
async def read_drawings(symbol: SymbolKey, response: Response, read: GetDep) -> Any:
    """Return the symbol's saved drawings and their revision (``ETag``)."""
    return await _read("symbol_drawings", symbol, response, read, SymbolDrawingsDocument)


@router.put(
    "/drawings/{symbol}",
    response_model=SymbolDrawingsDocument,
    responses=_PRECONDITION_RESPONSES,
)
async def save_drawings(
    symbol: SymbolKey,
    body: SymbolDrawingsV1,
    request: Request,
    response: Response,
    save: SaveDep,
    read: GetDep,
    if_match: IfMatch = None,
    if_none_match: IfNoneMatch = None,
) -> Any:
    """Save the symbol's drawings if they are still at the revision named in ``If-Match``."""
    return await _save(
        "symbol_drawings",
        symbol,
        body.model_dump(mode="json"),
        request,
        response,
        if_match,
        if_none_match,
        save,
        read,
        SymbolDrawingsDocument,
    )
