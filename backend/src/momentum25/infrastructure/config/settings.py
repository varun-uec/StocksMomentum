"""Centralized application settings, loaded from environment variables.

All configuration enters the application here (NFR-9). Settings use the ``M25_``
env prefix and are cached so the object is constructed once per process.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from momentum25.infrastructure.logging.setup import get_logger

_logger = get_logger("config")


class Settings(BaseSettings):
    """Strongly-typed application configuration.

    See ``IMPLEMENTATION_SPEC.md`` §12 (Configuration Model).
    """

    model_config = SettingsConfigDict(
        env_prefix="M25_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Environment ---
    environment: Literal["development", "test", "production"] = "development"

    # --- Persistence ---
    database_url: str = "postgresql+asyncpg://momentum25:momentum25@localhost:5432/momentum25"
    db_pool_size: int = 10
    db_max_overflow: int = 5
    db_echo: bool = False
    timescale_enabled: bool = False

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Market data / strategy ---
    data_provider: str = "bhavcopy"
    benchmark_index: str = "NIFTY500"
    strategy_dir: str = "../docs/architecture/strategies"

    # --- Zerodha Kite Connect (licensed feed, Phase 5.2) ---
    # ``kite_access_token`` is a *daily* token: Zerodha invalidates it at 6 AM
    # every day and recovery requires an interactive login (no refresh flow for
    # standard accounts), so it is configuration that changes daily, not a secret
    # set once at deploy time. Empty by default — the adapter is only usable
    # when all three are supplied.
    kite_api_key: str = ""
    kite_api_secret: str = ""
    kite_access_token: str = ""

    # --- Scheduler ---
    scheduler_enabled: bool = False
    schedule_cron: str = "30 18 * * 1-5"
    timezone: str = "Asia/Kolkata"

    # --- API / web ---
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # --- Observability ---
    log_level: str = "INFO"
    log_json: bool = True

    # --- Rate limiting ---
    rate_limit_max_requests: int = 200
    rate_limit_window_seconds: int = 60

    # --- Live single-symbol lookup (Phase 1.1/1.3) ---
    # Minimum seconds between NSE refreshes of the same symbol via the live
    # lookup endpoint -- prevents a client hammering ?refresh=true from
    # triggering an NSE round-trip on every request.
    live_refresh_cooldown_seconds: int = 300
    live_cache_ttl_seconds: int = 60

    # --- Retry configuration ---
    retry_max_attempts: int = 3
    retry_min_wait_seconds: float = 2.0
    retry_max_wait_seconds: float = 10.0
    request_timeout_seconds: float = 30.0

    # --- OpenTelemetry ---
    otel_enabled: bool = False
    otel_endpoint: str = "http://localhost:4318/v1/traces"
    otel_service_name: str = "momentum25"

    @property
    def is_production(self) -> bool:
        """Return ``True`` when running in the production environment."""
        return self.environment == "production"

    @field_validator("database_url")
    @classmethod
    def _validate_database_url(cls, v: str) -> str:
        """Ensure the database URL uses asyncpg driver in production."""
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "database_url must use 'postgresql+asyncpg://' driver (async)"
            )
        return v

    @field_validator("schedule_cron")
    @classmethod
    def _validate_cron(cls, v: str) -> str:
        """Validate crontab expression has exactly 5 fields."""
        parts = v.strip().split()
        if len(parts) != 5:
            raise ValueError(
                f"schedule_cron must have exactly 5 fields, got {len(parts)}: {v}"
            )
        return v

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        """Ensure the log level is a known value."""
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(
                f"log_level must be one of {allowed}, got {v}"
            )
        return upper

    @model_validator(mode="after")
    def _validate_retry_backoff(self) -> "Settings":
        """Ensure retry wait values are consistent."""
        if self.retry_min_wait_seconds >= self.retry_max_wait_seconds:
            raise ValueError(
                "retry_min_wait_seconds must be less than retry_max_wait_seconds"
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings singleton.

    Calls :meth:`Settings.model_dump` to trigger validation on first access
    and logs a structured summary of the effective configuration.
    """
    settings = Settings()
    _logger.info(
        "settings_loaded",
        environment=settings.environment,
        log_level=settings.log_level,
        database_url=settings.database_url,
        redis_url=settings.redis_url,
        scheduler_enabled=settings.scheduler_enabled,
        retry_max_attempts=settings.retry_max_attempts,
    )
    return settings
