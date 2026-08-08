"""Base contracts for chart pattern detectors.

Each pattern detector analyses a price series and returns a deterministic
PatternResult indicating whether the pattern is present, its quality score,
and human-readable evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class PatternResult:
    """Result of a single pattern detection attempt.

    ``detected``: Whether the pattern was positively identified.
    ``quality_score``: 0–100 score indicating how textbook the pattern is.
    ``explanation``: Human-readable description of the pattern evidence.
    ``metadata``: Additional context (e.g. pivot dates, price levels).
    """

    pattern_name: str
    detected: bool
    quality_score: int  # 0–100
    explanation: str
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class PatternDetector(Protocol):
    """Deterministic chart pattern detector."""

    pattern_name: str

    def detect(
        self, close: list[Decimal], high: list[Decimal], low: list[Decimal], volume: list[int]
    ) -> PatternResult:
        """Analyse price series and return detection result.

        Args:
            close: Closing prices (newest last).
            high: Daily highs.
            low: Daily lows.
            volume: Daily volumes.

        Returns:
            A PatternResult with ``detected``, ``quality_score``, and ``explanation``.
        """
        ...


@dataclass(frozen=True, slots=True)
class Pivot:
    """A swing high/low pivot point identified in the price series."""

    index: int
    price: Decimal
    pivot_type: str  # "high" or "low"
    strength: int  # 1–3, number of bars confirming on each side