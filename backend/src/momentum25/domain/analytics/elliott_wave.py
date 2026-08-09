"""Elliott Wave labelling of a price series — a chart annotation, not a signal.

The implementation lives in :mod:`momentum25.domain.analytics.elliott`, split by
responsibility (pivot detection, pattern rules, Fibonacci ratio analysis, wave
personality, candidate ranking, orchestration). This module is the stable import
surface: :mod:`momentum25.domain.analytics.chart_patterns` and the Elliott Wave
use case both import from here, so the package can be reorganised without
rippling through consumers.

Rule set / convention
---------------------
Rules and guidelines are taken from A.J. Frost & Robert Prechter, *Elliott Wave
Principle: Key to Market Behavior* (1978), cited lesson by lesson in each
submodule. Rules are binary and are never traded off against guidelines;
guidelines are measured, reported as evidence, and fed into a documented ranking.

Architectural constraint
------------------------
Nothing produced here — labels, projection zones, Fibonacci relationships,
personality evidence or the labelling-confidence score — is an input to the
Momentum25 score, the ranking, screening gates, the Trend Template, Relative
Strength, volume or pattern scores, buy-setup quality, stop-loss calculation, or
any production strategy decision. This surface emits no target price, no profit
projection, no R-multiple and no buy/sell verdict.

Everything is pure and deterministic: same bars in, same labels out. No I/O, no
clock, no randomness.
"""

from momentum25.domain.analytics.elliott import (
    DEFAULT_ZIGZAG_THRESHOLD_PCT,
    ConfidenceComponent,
    ElliottWaveAnalysis,
    FibonacciRelationship,
    GuidelineCheck,
    PersonalityCheck,
    PersonalityContext,
    Pivot,
    ProjectionZone,
    Subdivision,
    WaveCount,
    WaveLabel,
    analyze_elliott_wave,
    label_waves,
    zigzag_pivots,
)

__all__ = [
    "DEFAULT_ZIGZAG_THRESHOLD_PCT",
    "ConfidenceComponent",
    "ElliottWaveAnalysis",
    "FibonacciRelationship",
    "GuidelineCheck",
    "PersonalityCheck",
    "PersonalityContext",
    "Pivot",
    "ProjectionZone",
    "Subdivision",
    "WaveCount",
    "WaveLabel",
    "analyze_elliott_wave",
    "label_waves",
    "zigzag_pivots",
]
