"""``/portfolio``: the caller's CAS imports and portfolio analysis.

The statement travels in the request body (base64) with its password, is parsed in
memory, and is never written to disk, logs or the database; only its hash is kept.
"""

from __future__ import annotations

import base64
import binascii
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response
from pydantic import BaseModel, Field

from wickstreet.analytics.domain.screening import FilterError
from wickstreet.dependencies import Context, TenantSession
from wickstreet.portfolio.application.portfolio import PortfolioService
from wickstreet.portfolio.infrastructure.cas import CasparserReader
from wickstreet.portfolio.infrastructure.store import SqlLedger

router = APIRouter(prefix="/portfolio", tags=["mf-portfolio"])


class StatementIn(BaseModel):
    """A CAS PDF and its password; neither is stored."""

    pdf_base64: str = Field(repr=False)
    password: str = Field(repr=False)


def _service(request: Request, session: Any) -> PortfolioService:
    return PortfolioService(SqlLedger(session), CasparserReader(), request.app.state.fund_data)


def _content(body: StatementIn) -> bytes:
    try:
        return base64.b64decode(body.pdf_base64, validate=True)
    except (binascii.Error, ValueError):
        raise FilterError("pdf_base64", "the file is not valid base64") from None


def _target(text: str | None) -> dict[str, float] | None:
    if not text:
        return None
    try:
        parts = dict(item.split(":", 1) for item in text.split(","))
        target = {k.strip(): float(v) / 100 for k, v in parts.items()}
    except ValueError:
        raise FilterError("target", "write the target as Equity:60,Debt:40") from None
    if abs(sum(target.values()) - 1) > 0.001 or any(v < 0 for v in target.values()):
        raise FilterError("target", "target shares are 0 to 100 and add up to 100")
    return target


@router.post("/preview")
async def preview(
    body: StatementIn, request: Request, context: Context, session: TenantSession
) -> dict[str, Any]:
    """Parse a statement and report what an import would add; stores nothing."""
    return await _service(request, session).preview(context, _content(body), body.password)


@router.post("/imports", status_code=201)
async def commit(
    body: StatementIn, request: Request, context: Context, session: TenantSession
) -> dict[str, Any]:
    """Store a statement as one import; the same file again returns the same import."""
    return await _service(request, session).commit(context, _content(body), body.password)


@router.delete("/imports/{import_id}", status_code=204)
async def undo(
    import_id: UUID, request: Request, context: Context, session: TenantSession
) -> Response:
    """Remove an import and the transactions it added."""
    await _service(request, session).undo(context, import_id)
    return Response(status_code=204)


@router.get("")
async def view(
    request: Request,
    context: Context,
    session: TenantSession,
    target: Annotated[str | None, Query(description="Target mix, e.g. Equity:60,Debt:40.")] = None,
) -> dict[str, Any]:
    """Value, XIRR, allocation, costs, look-through, overlap, alternatives, rebalancing."""
    return await _service(request, session).view(context, _target(target))
