"""The Momentum25 database, built from application settings.

The engine and unit-of-work implementation live in ``platform_common.database``.
"""

from __future__ import annotations

from functools import lru_cache

from momentum25.infrastructure.config.settings import get_settings
from platform_common.database import Database

__all__ = ["Database", "get_database"]


@lru_cache(maxsize=1)
def get_database() -> Database:
    """Return the cached :class:`Database` singleton."""
    settings = get_settings()
    return Database(
        settings.database_url,
        echo=settings.db_echo,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
    )
