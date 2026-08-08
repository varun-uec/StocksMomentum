"""Run DTOs, summary value object, and the refresh-trigger request body."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


@dataclass(slots=True)
class ScreeningRunSummary:
    """Structured execution summary returned by the orchestrator (mutated in place)."""

    run_date: date
    total_evaluated: int = 0
    total_passed: int = 0
    total_skipped_insufficient_data: int = 0
    total_failed: int = 0
    duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)
    total_skipped_stale_data: int = 0
    # Securities excluded by the strategy's declared liquidity floor
    # (``config.universe``) rather than by data problems (Phase 0.1).
    total_skipped_ineligible_universe: int = 0


class RunDTO(BaseModel):
    """A screening run as exposed by the API."""

    id: int
    status: str
    run_date: date
    trigger: str
    strategy: str
    data_version: str
    config_hash: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    stats: dict[str, Any] | None = None
    error: str | None = None


class TriggerRefreshRequest(BaseModel):
    """Request body for ``POST /runs`` and ``POST /runs/execute``."""

    strategy: str = Field(..., description="Strategy name to run.")
    force: bool = Field(
        default=False,
        description=(
            "Re-fetch the full historical lookback window instead of only "
            "sessions since the last ingest (Phase 1.6 incremental fetch)."
        ),
    )
    background: bool = Field(
        default=True,
        description=(
            "POST /runs/execute only. If true (default), returns 202 with a "
            "PENDING run immediately and executes in the background -- poll "
            "GET /runs/{id}. If false, blocks and returns the COMPLETED run "
            "(201), matching the pre-Phase-1.6 behaviour used by tests/CLI."
        ),
    )