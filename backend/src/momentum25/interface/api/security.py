"""Authentication seam (ADR-010).

The MVP is unauthenticated. ``get_current_user`` returns a singleton anonymous user.
To enable auth later, replace this dependency with JWT/OAuth2 validation; no router or
use-case signatures change.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CurrentUser:
    """The authenticated principal. ``tenant_id`` is the SaaS scoping seam."""

    id: str
    is_anonymous: bool
    tenant_id: int | None = None


_ANONYMOUS = CurrentUser(id="anonymous", is_anonymous=True, tenant_id=None)


async def get_current_user() -> CurrentUser:
    """Return the current user (anonymous in the MVP)."""
    return _ANONYMOUS
