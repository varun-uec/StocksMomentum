"""Chart pattern detection framework.

Provides base contracts (PatternDetector, PatternResult) and concrete
deterministic implementations for common chart patterns.

Current implementations:
- Flat Base
- Ascending Base
- Cup with Handle
- Volatility Contraction Pattern (VCP)
- High Tight Flag
"""

from momentum25.domain.patterns.base import PatternResult, PatternDetector, Pivot
from momentum25.domain.patterns.registry import (
    PatternRegistry,
    register_builtin_patterns,
    get_pattern_registry,
)

__all__ = [
    "PatternResult",
    "PatternDetector",
    "Pivot",
    "PatternRegistry",
    "register_builtin_patterns",
    "get_pattern_registry",
]