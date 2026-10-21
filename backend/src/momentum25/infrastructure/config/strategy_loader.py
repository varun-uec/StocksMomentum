"""Strategy configuration loading, validation, and hashing.

Strategies are JSON files (the reference lives in
``docs/architecture/strategies``). This module validates raw JSON into a typed
:class:`~momentum25.domain.entities.strategy.StrategyConfig`, converts back to a
canonical dict for persistence, and computes a stable ``config_hash`` (ADR-009).

Pydantic is used here (infrastructure), keeping the domain free of framework deps.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as SchemaError

from momentum25.domain.entities.strategy import (
    EngineConfig,
    RuleConfig,
    Strategy,
    StrategyConfig,
)
from momentum25.domain.errors import ValidationError
from momentum25.domain.strategy.config_codec import compute_config_hash
from momentum25.domain.strategy.rule_schemas import validate_config


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
    """Validate and convert a raw config dict into a :class:`StrategyConfig`.

    Checks the shape only. Stored strategies are read through it, and a stored
    strategy stays readable as it was run (ADR-005), so the rule schemas are
    enforced where a strategy is written: :func:`checked_config`.
    """
    return _to_config(_StrategySchema.model_validate(raw))


def checked_config(raw: dict[str, Any]) -> StrategyConfig:
    """Convert a raw config and enforce the rule parameter schemas (ADR-014 §2).

    Raises :class:`ValidationError` listing every problem; nothing is clamped.
    """
    try:
        config = config_from_raw(raw)
    except SchemaError as exc:
        name = raw.get("name")
        problems = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        raise ValidationError(f"Strategy {name!r} is invalid: {problems}") from exc
    errors = validate_config(config)
    if errors:
        raise ValidationError(f"Strategy {config.name!r} is invalid: " + "; ".join(errors))
    return config


def load_strategy_file(path: Path) -> Strategy:
    """Load, validate, and hash a strategy JSON file into a :class:`Strategy`."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    # ``is_active`` and ``kind`` are deployment/lifecycle flags, not part of the
    # scored config (and thus excluded from ``config_hash``). Pop them before
    # config validation so they do not trip the config schema's extra-field
    # guard. Absent flag = active / production, preserving prior behaviour for
    # every strategy file that omits them.
    is_active = bool(raw.pop("is_active", True))
    kind = str(raw.pop("kind", "production"))
    config = checked_config(raw)
    return Strategy(
        name=config.name,
        version=config.version,
        config=config,
        config_hash=compute_config_hash(config),
        is_active=is_active,
        kind=kind,
    )


def load_strategies_dir(directory: Path) -> list[Strategy]:
    """Load all ``*.json`` strategies from a directory (sorted for determinism)."""
    return [load_strategy_file(p) for p in sorted(directory.glob("*.json"))]
