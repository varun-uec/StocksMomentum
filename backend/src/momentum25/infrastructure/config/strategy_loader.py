"""Strategy configuration loading, validation, and hashing.

Strategies are JSON files (the reference lives in
``docs/architecture/strategies``). This module validates raw JSON into a typed
:class:`~momentum25.domain.entities.strategy.StrategyConfig`, converts back to a
canonical dict for persistence, and computes a stable ``config_hash`` (ADR-009).

Pydantic is used here (infrastructure), keeping the domain free of framework deps.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from momentum25.domain.entities.strategy import (
    EngineConfig,
    RuleConfig,
    Strategy,
    StrategyConfig,
)


class _RuleSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    weight: Decimal = Decimal(1)
    params: dict[str, Any] = Field(default_factory=dict)
    gate: bool = False


class _EngineSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    enabled: bool = True
    weight: Decimal = Decimal(1)
    gate: bool = False
    rules: list[_RuleSchema] = Field(default_factory=list)


class _StrategySchema(BaseModel):
    """Validation schema for a raw strategy JSON document."""

    model_config = ConfigDict(extra="forbid")
    name: str
    version: int
    description: str | None = None
    benchmark_index: str | None = None
    universe: dict[str, Any] = Field(default_factory=dict)
    indicators: dict[str, Any] = Field(default_factory=dict)
    ranking: dict[str, Any] = Field(default_factory=dict)
    engines: list[_EngineSchema]
    scoring: dict[str, dict[str, Decimal]] = Field(default_factory=dict)


def _to_config(schema: _StrategySchema) -> StrategyConfig:
    """Convert a validated schema into the domain :class:`StrategyConfig`."""
    engines = tuple(
        EngineConfig(
            id=e.id,
            enabled=e.enabled,
            weight=e.weight,
            gate=e.gate,
            rules=tuple(
                RuleConfig(id=r.id, weight=r.weight, params=r.params, gate=r.gate)
                for r in e.rules
            ),
        )
        for e in schema.engines
    )
    return StrategyConfig(
        name=schema.name,
        version=schema.version,
        description=schema.description,
        benchmark_index=schema.benchmark_index,
        universe=schema.universe,
        indicators=schema.indicators,
        ranking=schema.ranking,
        engines=engines,
        momentum_weights=schema.scoring.get("momentum_weights", {}),
        buy_setup_weights=schema.scoring.get("buy_setup_weights", {}),
    )


def config_from_raw(raw: dict[str, Any]) -> StrategyConfig:
    """Validate and convert a raw config dict into a :class:`StrategyConfig`."""
    return _to_config(_StrategySchema.model_validate(raw))


def raw_from_config(config: StrategyConfig) -> dict[str, Any]:
    """Serialize a :class:`StrategyConfig` back to a canonical JSON-able dict."""
    return {
        "name": config.name,
        "version": config.version,
        "description": config.description,
        "benchmark_index": config.benchmark_index,
        "universe": config.universe,
        "indicators": config.indicators,
        "ranking": config.ranking,
        "engines": [
            {
                "id": e.id,
                "enabled": e.enabled,
                "weight": str(e.weight),
                "gate": e.gate,
                "rules": [
                    {"id": r.id, "weight": str(r.weight), "params": r.params, "gate": r.gate}
                    for r in e.rules
                ],
            }
            for e in config.engines
        ],
        "scoring": {
            "momentum_weights": {k: str(v) for k, v in config.momentum_weights.items()},
            "buy_setup_weights": {k: str(v) for k, v in config.buy_setup_weights.items()},
        },
    }


def compute_config_hash(config: StrategyConfig) -> str:
    """Compute a stable SHA-256 hash of the canonical config (run identity, ADR-009)."""
    canonical = json.dumps(raw_from_config(config), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def load_strategy_file(path: Path) -> Strategy:
    """Load, validate, and hash a strategy JSON file into a :class:`Strategy`."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    # ``is_active`` is a deployment/lifecycle flag, not part of the scored config
    # (and thus excluded from ``config_hash``). Pop it before config validation so
    # it does not trip the config schema's extra-field guard. Absent flag = active,
    # preserving prior behaviour for every strategy file that omits it.
    is_active = bool(raw.pop("is_active", True))
    config = config_from_raw(raw)
    return Strategy(
        name=config.name,
        version=config.version,
        config=config,
        config_hash=compute_config_hash(config),
        is_active=is_active,
    )


def load_strategies_dir(directory: Path) -> list[Strategy]:
    """Load all ``*.json`` strategies from a directory (sorted for determinism)."""
    return [load_strategy_file(p) for p in sorted(directory.glob("*.json"))]
