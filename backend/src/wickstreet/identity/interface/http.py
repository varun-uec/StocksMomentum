"""``GET /me``: the verified principal the request acts as."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from wickstreet.dependencies import Context, TenantSession
from wickstreet.identity.application.principals import VerifyPrincipal
from wickstreet.identity.domain.principals import UnknownPrincipalError
from wickstreet.identity.infrastructure.registry import SqlPrincipalRegistry

router = APIRouter(tags=["identity"])


class PrincipalOut(BaseModel):
    """The tenant and user a request acts as."""

    tenant_id: UUID
    user_id: UUID


@router.get("/me")
async def me(context: Context, session: TenantSession) -> PrincipalOut:
    """Return the request's principal; 403 when it is not registered in its tenant."""
    try:
        verified = await VerifyPrincipal(SqlPrincipalRegistry(session)).execute(context)
    except UnknownPrincipalError:
        raise HTTPException(status_code=403, detail="Unknown principal.") from None
    return PrincipalOut(tenant_id=verified.tenant_id, user_id=verified.user_id)
