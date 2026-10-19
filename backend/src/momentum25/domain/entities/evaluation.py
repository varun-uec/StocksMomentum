"""Strategy evaluations (ADR-014 §5–7): one run of a user strategy in one result class."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

from momentum25.domain.research.strategy_evaluation import ResultClass

EvaluationStatus = Literal["queued", "running", "completed", "failed"]


@dataclass(frozen=True, slots=True)
class Evaluation:
    """An evaluation and, once it completes, its result body."""

    id: int
    family_id: int
    config_hash: str
    result_class: ResultClass
    window_start: date
    window_end: date
    data_version: str
    status: EvaluationStatus
    progress_done: int
    progress_total: int
    result: dict[str, Any] | None
    error: str | None
    created_at: datetime
    completed_at: datetime | None
