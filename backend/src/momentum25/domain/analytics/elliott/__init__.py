"""Elliott Wave labelling — a chart annotation, never a signal.

The package is split by responsibility so that each concern cites its own source
and can be read on its own:

``pivots``
    Confirmed swing detection (percentage-reversal zigzag).
``patterns``
    The rule sets of every modelled Elliott structure, each citing Frost &
    Prechter by lesson. Rules are binary; guidelines are reported, never enforced.
``fibonacci``
    Price *and* time ratio analysis between labelled turning points, plus the
    range-only projection zone.
``personality``
    Cross-checks of each labelled wave position against the volume, RSI and ADX
    already computed by the platform (Lesson 14, "Wave Personality").
``ranking``
    The documented two-stage candidate ordering and the
    confidence-in-*labelling* score.
``analysis``
    Orchestration: pivots -> candidates -> ranking -> recursive degree hierarchy.

Architectural constraint, restated because it is load-bearing: nothing in this
package is an input to the Momentum25 score, the ranking, the screening gates,
the Trend Template, Relative Strength, buy-setup quality, stop-loss calculation
or any production strategy decision. It produces labels, evidence and ranges —
never a target price, a profit projection or a buy/sell verdict.

Everything here is pure and deterministic: same bars in, same output out. No
I/O, no clock, no randomness.
"""

from momentum25.domain.analytics.elliott.analysis import (
    ElliottWaveAnalysis,
    Subdivision,
    WaveCount,
    WaveLabel,
    analyze_elliott_wave,
    label_waves,
)
from momentum25.domain.analytics.elliott.fibonacci import (
    FibonacciRelationship,
    ProjectionZone,
)
from momentum25.domain.analytics.elliott.patterns import GuidelineCheck
from momentum25.domain.analytics.elliott.personality import (
    PersonalityCheck,
    PersonalityContext,
)
from momentum25.domain.analytics.elliott.pivots import (
    DEFAULT_ZIGZAG_THRESHOLD_PCT,
    Pivot,
    zigzag_pivots,
)
from momentum25.domain.analytics.elliott.ranking import ConfidenceComponent

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
