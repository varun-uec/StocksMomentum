"""System clock adapter implementing the :class:`Clock` port."""

from __future__ import annotations

from datetime import UTC, date, datetime


class SystemClock:
    """A :class:`~momentum25.domain.ports.clock.Clock` backed by the OS clock."""

    def today(self) -> date:
        """Return the current UTC date."""
        return datetime.now(UTC).date()

    def now(self) -> datetime:
        """Return the current timezone-aware UTC timestamp."""
        return datetime.now(UTC)
