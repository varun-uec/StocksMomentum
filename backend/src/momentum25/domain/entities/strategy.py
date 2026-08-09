"""Strategy entities: the configurable, versioned screening definition (ADR-005).

A ``Strategy`` is data, not code. It lists which engines are enabled, their rules,
thresholds, weights, and gates. Validation of the raw config into these typed
objects is performed by the strategy loader (infrastructure) using a Pydantic schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class RuleConfig:
    """Configuration for a single rule within an engine."""

    id: str
    weight: Decimal
    params: dict[str, Any] = field(default_factory=dict)
    gate: bool = False


@dataclass(frozen=True, slots=True)
class EngineConfig:
    """Configuration for a single evaluation engine within a strategy."""

    id: str
    enabled: bool
    weight: Decimal
    rules: tuple[RuleConfig, ...] = ()
    gate: bool = False


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    """The full, validated configuration body of a strategy."""

    name: str
    version: int
    engines: tuple[EngineConfig, ...]
    momentum_weights: dict[str, Decimal] = field(default_factory=dict)
    buy_setup_weights: dict[str, Decimal] = field(default_factory=dict)
    universe: dict[str, Any] = field(default_factory=dict)
    indicators: dict[str, Any] = field(default_factory=dict)
    ranking: dict[str, Any] = field(default_factory=dict)
    description: str | None = None
    benchmark_index: str | None = None

    def enabled_engines(self) -> tuple[EngineConfig, ...]:
        """Return enabled engines in a deterministic (config) order."""
        return tuple(e for e in self.engines if e.enabled)


@dataclass(frozen=True, slots=True)
class Strategy:
    """A persisted, hashed strategy definition."""

    name: str
    version: int
    config: StrategyConfig
    config_hash: str
    id: int | None = None
    is_active: bool = True
    kind: str = "production"
