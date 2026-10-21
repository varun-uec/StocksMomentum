"""Canonical serialization and hashing of a strategy config (ADR-009).

Pure functions of the domain entity. The ``config_hash`` is run identity, so
the one canonical form lives here, where every layer can reach it.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from momentum25.domain.entities.strategy import StrategyConfig


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
