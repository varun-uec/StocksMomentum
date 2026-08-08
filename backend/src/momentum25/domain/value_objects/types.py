"""Primitive value-object types shared across the domain."""

from __future__ import annotations

import re
from enum import StrEnum

_SYMBOL_RE = re.compile(r"^[A-Z0-9&\-]{1,20}$")


class Symbol(str):
    """A validated, uppercase NSE trading symbol.

    Raises:
        ValueError: If the value is not a valid symbol.
    """

    __slots__ = ()

    def __new__(cls, value: str) -> Symbol:
        """Create a normalized, validated symbol."""
        normalized = value.strip().upper()
        if not _SYMBOL_RE.match(normalized):
            raise ValueError(f"Invalid symbol: {value!r}")
        return super().__new__(cls, normalized)


class RunStatus(StrEnum):
    """Lifecycle states of a screening run (see ADD §16 state machine)."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RunTrigger(StrEnum):
    """How a screening run was initiated."""

    SCHEDULED = "SCHEDULED"
    MANUAL = "MANUAL"
