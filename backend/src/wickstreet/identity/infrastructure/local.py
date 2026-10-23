"""Personal-mode identity: one fixed tenant and user, no login (ADR-023 §2.2, U6).

Only the composition root selects it, and only in personal mode, which binds to
loopback (OM-2). The ids are fixed so the app finds the same records after every
restart; they are UUIDv5 of ``urn:wickstreet:personal:tenant`` and ``...:user``.
"""

from __future__ import annotations

from uuid import UUID

from starlette.requests import Request

from wickstreet.context import TenantContext

PERSONAL_CONTEXT = TenantContext(
    tenant_id=UUID("5bb771e7-1b5c-546f-a5ad-3e8f50c8d7b0"),
    user_id=UUID("7ce9931b-754b-5f38-9ff5-4548fd800048"),
)


async def authenticate_local(request: Request) -> TenantContext:
    """Return the owner's context for every request."""
    return PERSONAL_CONTEXT
