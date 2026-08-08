"""The ``ScreeningRun`` entity — an immutable snapshot of one screening execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from momentum25.domain.value_objects.types import RunStatus, RunTrigger


@dataclass(slots=True)
class ScreeningRun:
    """Metadata for a screening run.

    Run identity is ``(strategy_id, run_date, data_version, config_hash)`` (ADR-009).
    Result rows (scores, rule results) are persisted separately and are append-only;
    a run is immutable once :attr:`status` is ``COMPLETED`` (ADR-006).
    """

    strategy_id: int
    run_date: date
    data_version: str
    config_hash: str
    trigger: RunTrigger
    status: RunStatus = RunStatus.PENDING
    id: int | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    stats: dict[str, Any] = field(default_factory=dict)
