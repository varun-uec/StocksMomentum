"""Pattern registry — maps ``pattern_name`` to a :class:`PatternDetector`.

Engines use this registry to discover and run pattern detectors without
hard-coding dependencies.
"""

from __future__ import annotations

from momentum25.domain.patterns.base import PatternDetector

_detectors: dict[str, PatternDetector] = {}


class PatternRegistry:
    """An in-memory registry of pattern detectors keyed by ``pattern_name``."""

    def register(self, detector: PatternDetector) -> PatternDetector:
        """Register a pattern detector. Silently replaces if already registered."""
        _detectors[detector.pattern_name] = detector
        return detector

    def get(self, pattern_name: str) -> PatternDetector | None:
        """Return the detector for ``pattern_name`` or ``None``."""
        return _detectors.get(pattern_name)

    def list(self) -> list[str]:
        """Return all registered pattern names in sorted order."""
        return sorted(_detectors)

    def all_detectors(self) -> dict[str, PatternDetector]:
        """Return a copy of all registered detectors."""
        return dict(_detectors)

    def clear(self) -> None:
        """Clear all registered detectors (useful for testing)."""
        _detectors.clear()


_pattern_registry = PatternRegistry()


def get_pattern_registry() -> PatternRegistry:
    """Return the application-wide pattern registry singleton."""
    return _pattern_registry


def register_builtin_patterns() -> None:
    """Register all built-in pattern detectors."""
    # Lazy imports to avoid circular dependencies
    from momentum25.domain.patterns.flat_base import FlatBaseDetector
    from momentum25.domain.patterns.ascending_base import AscendingBaseDetector
    from momentum25.domain.patterns.cup_handle import CupWithHandleDetector
    from momentum25.domain.patterns.vcp import VCPDetector

    registry = get_pattern_registry()
    registry.register(FlatBaseDetector())
    registry.register(AscendingBaseDetector())
    registry.register(CupWithHandleDetector())
    registry.register(VCPDetector())