"""Wickstreet 2.0 settings, read once at startup from ``WICKSTREET_*`` variables.

``mode`` selects adapters in the composition root only (ADR-023 §2.1, §2.2).
Domain and application code never read it (OM-1).
"""

from __future__ import annotations

import ipaddress
from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Mode = Literal["personal", "saas"]


def is_loopback(host: str) -> bool:
    """Return whether ``host`` (a name or address, IPv6 with or without brackets) is loopback."""
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


class WickstreetSettings(BaseSettings):
    """Typed configuration for the MF application."""

    model_config = SettingsConfigDict(
        env_prefix="WICKSTREET_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mode: Mode = "personal"

    # Runtime login: wickstreet_app, never the schema owner or a superuser (ADR-023 U3).
    database_url: str = (
        "postgresql+asyncpg://wickstreet_app:wickstreet_app@localhost:5432/momentum25"
    )
    # Owner login, used only by the MF Alembic environment and `wickstreet db-roles`.
    migration_database_url: str = (
        "postgresql+asyncpg://wickstreet_owner:wickstreet_owner@localhost:5432/momentum25"
    )
    db_pool_size: int = 5
    db_max_overflow: int = 5

    # Host names (no ports) the MF app answers to (ADR-012 guard).
    allowed_hosts: list[str] = Field(default_factory=lambda: ["localhost", "127.0.0.1", "[::1]"])

    # Where `python -m apphost` binds, and how a container publishes it (ADR-023 U8).
    bind_host: str = "127.0.0.1"
    bind_port: int = 8000
    in_container: bool = False
    # The host address Docker publishes the port on (Compose passes APP_BIND).
    published_bind: str | None = None

    @model_validator(mode="after")
    def _personal_mode_is_loopback_only(self) -> WickstreetSettings:
        """Refuse any network exposure in personal mode (ADR-023 OM-2, U8).

        Outside a container the bind address must be loopback. Inside one the app
        binds every interface of the container, so the published address must be
        loopback instead, and it must be stated.
        """
        if self.mode != "personal":
            return self
        if self.in_container:
            if self.published_bind is None or not is_loopback(self.published_bind):
                raise ValueError(
                    "Personal mode publishes on loopback only: set APP_BIND (Compose) or "
                    f"WICKSTREET_PUBLISHED_BIND to 127.0.0.1, not {self.published_bind!r}."
                )
        elif not is_loopback(self.bind_host):
            raise ValueError(
                "Personal mode binds to loopback only: set WICKSTREET_BIND_HOST to "
                f"127.0.0.1, not {self.bind_host!r}."
            )
        return self


@lru_cache(maxsize=1)
def get_settings() -> WickstreetSettings:
    """Return the cached settings."""
    return WickstreetSettings()
