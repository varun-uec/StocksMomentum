"""Strategy DTOs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class StrategySummaryDTO(BaseModel):
    """A strategy summary (list view)."""

    id: int
    name: str
    version: int
    is_active: bool
    kind: str
    config_hash: str
    description: str | None = None


class StrategyDetailDTO(StrategySummaryDTO):
    """A strategy with its full configuration body."""

    config: dict[str, Any]
