"""User documents: the owner's saved workspace and drawings (ADR-013 §5).

A document is user data, not market data. It holds no business rule and never
feeds a score, gate or rank. ``revision`` starts at 1 and rises by one on every
save; a save names the revision it was based on, so two windows can never
overwrite each other silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

DocumentKind = Literal["workspace", "symbol_drawings"]


@dataclass(frozen=True, slots=True)
class UserDocument:
    """One stored document and the revision it is at."""

    kind: DocumentKind
    key: str
    body: dict[str, Any]
    schema_version: int
    revision: int
    updated_at: datetime
