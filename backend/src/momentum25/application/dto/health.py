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


class DataFreshnessDTO(BaseModel):
    """Whether persisted market data is current, and why if not (Phase 1.5).

    ``classification`` distinguishes an expected gap (``MARKET_CLOSED`` --
    weekend or NSE holiday) from a real one (``STALE`` -- ingestion is behind
    or has stopped), so a client never has to guess which one a bare
    timestamp means.
    """

    latest_bar_date: date | None
    as_of: date
    sessions_missed: int
    classification: str  # "FRESH" | "MARKET_CLOSED" | "STALE"
    next_session: date | None
    calendar_source: str = "XBOM (NSE observes the same trading holidays)"