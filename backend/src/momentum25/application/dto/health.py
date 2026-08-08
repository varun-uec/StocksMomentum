"""Health-check DTOs for liveness, readiness, and startup probes."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class HealthDTO(BaseModel):
    """Service health snapshot (legacy combined endpoint)."""

    status: str
    db: str
    redis: str
    latest_run: date | None = None
    version: str


class LivenessDTO(BaseModel):
    """Liveness probe — confirms the process is alive and serving."""

    status: str = "ok"
    version: str
    uptime_seconds: float
    started_at: datetime


class ReadinessDTO(BaseModel):
    """Readiness probe — confirms dependencies are reachable."""

    status: str
    db: str
    redis: str
    version: str


class StartupDTO(BaseModel):
    """Startup probe — confirms initialization completed successfully."""

    status: str
    version: str
    strategies_loaded: int
    engines_registered: int