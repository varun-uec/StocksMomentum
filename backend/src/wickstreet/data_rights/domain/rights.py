"""Uses of a data source and the rule that unknown means denied (ADR-023 §2.3, ADR-017 MF-13)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class Use(StrEnum):
    """One permitted use of a data source (ADR-022 §2.11)."""

    AUTOMATED_RETRIEVAL = "automated_retrieval"
    STORAGE = "storage"
    DISPLAY = "display"
    DERIVED_METRICS = "derived_metrics"
    EXPORT = "export"
    AI_PROCESSING_INTERNAL = "ai_processing_internal"
    AI_PROCESSING_EXTERNAL = "ai_processing_external"


@dataclass(frozen=True, slots=True)
class Grant:
    """A recorded right: who may use ``source`` for ``use``, and on what basis."""

    id: int
    source: str
    use: Use
    basis: str


class RightsDeniedError(Exception):
    """No grant is recorded for this source and use."""

    def __init__(self, source: str, use: Use) -> None:
        """Name the missing right."""
        super().__init__(f"No recorded right to use {source!r} for {use.value}.")
        self.source = source
        self.use = use


class RightsRegister(Protocol):
    """Port for the recorded grants."""

    async def grant_for(self, source: str, use: Use) -> Grant | None:
        """Return the active grant for ``source`` and ``use``, or ``None``."""
        ...
