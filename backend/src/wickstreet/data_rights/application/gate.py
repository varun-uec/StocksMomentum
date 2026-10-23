"""The rights gate every acquisition, storage, display and model step asks first."""

from __future__ import annotations

from wickstreet.data_rights.domain.rights import Grant, RightsDeniedError, RightsRegister, Use


class RightsGate:
    """Fail closed: a use without a recorded grant raises :class:`RightsDeniedError`."""

    def __init__(self, register: RightsRegister) -> None:
        """Create the gate over a register."""
        self._register = register

    async def require(self, source: str, use: Use) -> Grant:
        """Return the grant for ``source`` and ``use``, or raise."""
        grant = await self._register.grant_for(source, use)
        if grant is None:
            raise RightsDeniedError(source, use)
        return grant
