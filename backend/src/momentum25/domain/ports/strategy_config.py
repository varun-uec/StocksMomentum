"""Port: check a raw strategy config document and convert it to a domain config."""

from __future__ import annotations

from typing import Any, Protocol

from momentum25.domain.entities.strategy import StrategyConfig


class StrategyConfigChecker(Protocol):
    """Validate shape and rule parameter schemas (ADR-014 §2).

    Raises :class:`~momentum25.domain.errors.ValidationError` listing every problem.
    """

    def __call__(self, raw: dict[str, Any]) -> StrategyConfig:
        """Return the config for *raw*, or raise."""
        ...
