"""The principal registry: which users belong to which tenant (ADR-023 §2.6, U6)."""

from __future__ import annotations

from typing import Protocol

from wickstreet.context import TenantContext


class UnknownPrincipalError(Exception):
    """The context names a user that is not registered in that tenant."""


class PrincipalRegistry(Protocol):
    """Port for the tenant and user records."""

    async def register(self, context: TenantContext) -> None:
        """Record the tenant and its user; a no-op when both exist."""
        ...

    async def contains(self, context: TenantContext) -> bool:
        """Return whether the user is registered in the context's tenant."""
        ...
