"""Registers all built-in evaluation engines into an :class:`EngineRegistry`.

Called once at application startup. Adding a new engine means adding one line here
(and its module), with no other wiring changes (ADR-005).
"""

from __future__ import annotations

from momentum25.domain.engines.breakout import BreakoutEngine
from momentum25.domain.engines.fundamental import FundamentalEngine
from momentum25.domain.engines.momentum_quality import MomentumQualityEngine
from momentum25.domain.engines.pattern import PatternEngine
from momentum25.domain.engines.relative_strength import RelativeStrengthEngine
from momentum25.domain.engines.risk import RiskEngine
from momentum25.domain.engines.trend_template import TrendTemplateEngine
from momentum25.domain.engines.volume_accumulation import VolumeAccumulationEngine
from momentum25.domain.strategy.engine_registry import EngineRegistry, engine_registry


def register_builtin_engines(registry: EngineRegistry | None = None) -> EngineRegistry:
    """Register all built-in engines into ``registry`` (default: the global one)."""
    reg = registry or engine_registry
    for engine in (
        TrendTemplateEngine(),
        RelativeStrengthEngine(),
        VolumeAccumulationEngine(),
        PatternEngine(),
        BreakoutEngine(),
        MomentumQualityEngine(),
        RiskEngine(),
        FundamentalEngine(),
    ):
        if not reg.has(engine.engine_id):
            reg.register(engine)

    # Register built-in pattern detectors
    from momentum25.domain.patterns.registry import register_builtin_patterns

    register_builtin_patterns()

    return reg
