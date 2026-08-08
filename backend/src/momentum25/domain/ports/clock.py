"""Clock port — abstracts wall-clock access out of the pure core (ADR-009)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """Provides the current date/time. Injected so the core stays deterministic."""

    def today(self) -> date:
        """Return the current date."""
        ...

    def now(self) -> datetime:
        """Return the current timezone-aware timestamp."""
        ...
