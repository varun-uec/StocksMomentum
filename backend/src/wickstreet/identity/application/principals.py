"""Register a principal, and verify the principal a request acts as."""

from __future__ import annotations

from wickstreet.context import TenantContext
from wickstreet.identity.domain.principals import PrincipalRegistry, UnknownPrincipalError


class RegisterPrincipal:
    """Record a tenant and its user."""

    def __init__(self, registry: PrincipalRegistry) -> None:
        """Create the use case over a registry."""
        self._registry = registry

    async def execute(self, context: TenantContext) -> None:
        """Register ``context``; repeating it changes nothing."""
        await self._registry.register(context)


class VerifyPrincipal:
    """Confirm that the context's user is registered in the context's tenant."""

    def __init__(self, registry: PrincipalRegistry) -> None:
        """Create the use case over a registry."""
        self._registry = registry

    async def execute(self, context: TenantContext) -> TenantContext:
        """Return ``context``, or raise :class:`UnknownPrincipalError`."""
        if not await self._registry.contains(context):
            raise UnknownPrincipalError
        return context
