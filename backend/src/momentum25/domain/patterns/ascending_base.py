"""Ascending Base pattern detector.

An ascending base is a consolidation where each pullback bottom is higher
than the previous one, with overall price trending sideways to slightly up.
Base depth is typically 10–20%.

Rules:
- Each successive low is higher than the previous low (higher lows)
- Base depth ≤ 25% from highest high to lowest low
- Minimum 3 weeks (15 days) of consolidation
"""

from __future__ import annotations

from decimal import Decimal

from momentum25.domain.patterns.base import PatternDetector, PatternResult


class AscendingBaseDetector:
    """Detects an Ascending Base consolidation pattern."""

    pattern_name = "ascending_base"

    _MAX_DEPTH_PCT = Decimal("25")
    _MIN_BASE_LENGTH = 15
    _MAX_BASE_LENGTH = 65
    _MIN_PULLBACKS = 3  # Minimum higher lows for confirmation

    def detect(
        self,
        close: list[Decimal],
        high: list[Decimal],
        low: list[Decimal],
        volume: list[int],
    ) -> PatternResult:
        if len(close) < self._MIN_BASE_LENGTH + 30:
            return PatternResult(
                pattern_name=self.pattern_name,
                detected=False,
                quality_score=0,
                explanation="Insufficient data: need at least 45 bars.",
            )

        lookback = min(len(close), self._MAX_BASE_LENGTH + 30)
        recent_low = low[-lookback:]
        recent_high = high[-lookback:]

        # Partition into segments to find higher lows
        segment_size = max(len(recent_low) // 4, 5)
        lows_per_segment: list[Decimal] = []
        for i in range(0, len(recent_low), segment_size):
            seg = recent_low[i : i + segment_size]
            if seg:
                lows_per_segment.append(min(seg))

        # Check for higher lows
        higher_lows = sum(
            1 for i in range(1, len(lows_per_segment))
            if lows_per_segment[i] > lows_per_segment[i - 1]
        )

        if higher_lows < self._MIN_PULLBACKS - 1:
            return PatternResult(
                pattern_name=self.pattern_name,
                detected=False,
                quality_score=0,
                explanation=(
                    f"Found only {higher_lows} higher low transitions, "
                    f"need ≥ {self._MIN_PULLBACKS - 1}."
                ),
            )

        # Check overall depth
        overall_high = max(recent_high)
        overall_low = min(recent_low)
        depth_pct = (overall_high - overall_low) / overall_high * Decimal("100")

        if depth_pct > self._MAX_DEPTH_PCT:
            return PatternResult(
                pattern_name=self.pattern_name,
                detected=False,
                quality_score=0,
                explanation=(
                    f"Base depth {depth_pct:.1f}% exceeds max {self._MAX_DEPTH_PCT}%."
                ),
            )

        # Quality score based on low count and depth
        quality_score = min(100, int(higher_lows * 20 + max(0, 100 - int(depth_pct))))

        return PatternResult(
            pattern_name=self.pattern_name,
            detected=True,
            quality_score=quality_score,
            explanation=(
                f"Ascending Base detected: {higher_lows} higher low segments, "
                f"{depth_pct:.1f}% depth, quality {quality_score}/100."
            ),
            metadata={
                "higher_low_segments": higher_lows,
                "depth_pct": float(depth_pct),
            },
        )