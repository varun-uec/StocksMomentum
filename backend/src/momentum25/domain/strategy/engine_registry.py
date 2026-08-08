"""The engine registry — maps ``engine_id`` to an :class:`EvaluationEngine`."""

from __future__ import annotations

from momentum25.domain.engines.base import EvaluationEngine
from momentum25.domain.errors import DomainError


class EngineRegistry:
    """An in-memory registry of evaluation engines keyed by ``engine_id``."""

    def __init__(self) -> None:
        """Create an empty registry."""
        self._engines: dict[str, EvaluationEngine] = {}

    def register(self, engine: EvaluationEngine) -> EvaluationEngine:
        """Register an engine. Raises if the ``engine_id`` is already taken."""
        if engine.engine_id in self._engines:
            raise DomainError(f"Duplicate engine_id: {engine.engine_id}")
        self._engines[engine.engine_id] = engine
        return engine

    def get(self, engine_id: str) -> EvaluationEngine:
        """Return the engine for ``engine_id`` or raise :class:`DomainError`."""
        try:
            return self._engines[engine_id]
        except KeyError as exc:
            raise DomainError(f"Unknown engine_id: {engine_id}") from exc

    def has(self, engine_id: str) -> bool:
        """Return whether ``engine_id`` is registered."""
        return engine_id in self._engines

    def all_ids(self) -> list[str]:
        """Return all registered engine ids in sorted order."""
        return sorted(self._engines)


engine_registry = EngineRegistry()
