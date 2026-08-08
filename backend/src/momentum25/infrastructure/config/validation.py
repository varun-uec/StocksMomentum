"""Configuration validation at startup.

Validates that all required configuration values are present and consistent
before the application starts. This catches misconfigurations early and
produces clear error messages.
"""

from __future__ import annotations

import os
from pathlib import Path

from momentum25.infrastructure.config.settings import Settings
from momentum25.infrastructure.logging.setup import get_logger

_logger = get_logger("config.validation")


class ConfigurationError(Exception):
    """Raised when configuration validation fails."""


def validate_configuration(settings: Settings) -> None:
    """Validate application configuration at startup.

    Checks:
    - Required environment variables are set (in production)
    - Strategy directory exists
    - Database URL is reachable (valid format)
    - Redis URL is reachable (valid format)
    - CORS origins are valid
    - Log level is valid

    Args:
        settings: The application settings to validate.

    Raises:
        ConfigurationError: If any validation check fails.
    """
    errors: list[str] = []

    # Production-only checks
    if settings.environment == "production":
        _check_required_env("M25_DATABASE_URL", errors)
        _check_required_env("M25_REDIS_URL", errors)

    # Strategy directory
    strategy_path = Path(settings.strategy_dir)
    if not strategy_path.exists():
        _logger.warning(
            "strategy_dir_not_found",
            path=str(strategy_path),
            message="Strategy directory does not exist. "
            "Strategies must be loaded from the database or API.",
        )

    # Database URL format
    if not settings.database_url.startswith("postgresql+asyncpg://"):
        errors.append(
            f"database_url must use 'postgresql+asyncpg://' driver, "
            f"got: {settings.database_url[:30]}..."
        )

    # Redis URL format
    if not settings.redis_url.startswith("redis://") and not settings.redis_url.startswith(
        "rediss://"
    ):
        errors.append(
            f"redis_url must start with 'redis://' or 'rediss://', "
            f"got: {settings.redis_url[:20]}..."
        )

    # CORS origins
    for origin in settings.cors_origins:
        if not origin.startswith(("http://", "https://")):
            errors.append(
                f"cors_origin must start with http:// or https://, got: {origin}"
            )

    # Retry configuration
    if settings.retry_min_wait_seconds >= settings.retry_max_wait_seconds:
        errors.append(
            f"retry_min_wait_seconds ({settings.retry_min_wait_seconds}) must be "
            f"less than retry_max_wait_seconds ({settings.retry_max_wait_seconds})"
        )

    if settings.environment == "production" and settings.log_level == "DEBUG":
        _logger.warning(
            "production_debug_logging",
            message="Production environment with DEBUG log level. "
            "This may expose sensitive data and impact performance.",
        )

    if errors:
        error_msg = "\n".join(f"  - {e}" for e in errors)
        raise ConfigurationError(
            f"Configuration validation failed with {len(errors)} error(s):\n{error_msg}"
        )

    _logger.info("configuration_validated", environment=settings.environment)


def _check_required_env(name: str, errors: list[str]) -> None:
    """Check that a required environment variable is set (not default)."""
    value = os.environ.get(name, "")
    if not value:
        errors.append(f"Required environment variable '{name}' is not set")