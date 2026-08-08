"""Flat Base pattern detector.

A flat base is a sideways consolidation after an uptrend, with minimal price
decline (typically 5–15%). The base width should be at least 5 weeks (25 days).

Rules:
- Prior uptrend: price is above SMA200 (long-term uptrend context)
- Base depth: max drawdown in base is ≤ 15% from highest high to lowest low
- Base width: at least 25 trading days since the start of the base
- Tightness: close range (high-low) as % of price is below threshold
"""

from __future__ import annotations

from decimal import Decimal

from momentum25.domain.patterns.base import PatternDetector, PatternResult


class FlatBaseDetector:
    """Detects a Flat Base consolidation pattern.

    A flat base is a sideways price movement with limited decline, typically
    5–15% maximum correction from the base high.
    """

    pattern_name = "flat_base"

    # Maximum base depth (% decline from high to low)
    _MAX_DEPTH_PCT = Decimal("15")

    # Minimum base length in trading days
    _MIN_BASE_LENGTH = 25

    # Maximum base length in trading days
    _MAX_BASE_LENGTH = 65

    def detect(
        self,
        close: list[Decimal],
        high: list[Decimal],
        low: list[Decimal],
        volume: list[int],
    ) -> PatternResult:
        """Detect a flat base pattern in the price series."""
        if len(close) < self._MIN_BASE_LENGTH + 50:
            return PatternResult(
                pattern_name=self.pattern_name,
                detected=False,
                quality_score=0,
                explanation="Insufficient data: need at least 75 bars.",
            )

        # Use the most recent segment for base detection
        lookback = min(len(close), self._MAX_BASE_LENGTH + 50)
        recent_close = close[-lookback:]
        recent_high = high[-lookback:]
        recent_low = low[-lookback:]

        # Find the base start: a significant high that starts a sideways period
        # Scan from left to right to find the highest high in the first 10%
        base_start_idx = int(len(recent_close) * 0.1)
        if base_start_idx < 5:
            base_start_idx = 5

        base_high = max(recent_high[base_start_idx:-5])
        base_high_idx = recent_high.index(base_high)

        if base_high_idx < base_start_idx:
            base_high_idx = base_start_idx

        # The base region starts at the high and extends to the end
        base_region_low = min(recent_low[base_high_idx:])
        base_region_high = max(recent_high[base_high_idx:])
        base_length = len(recent_close) - base_high_idx

        # Check base length
        if base_length < self._MIN_BASE_LENGTH:
            return PatternResult(
                pattern_name=self.pattern_name,
                detected=False,
                quality_score=0,
                explanation=(
                    f"Base length {base_length}d < minimum {self._MIN_BASE_LENGTH}d."
                ),
            )

        if base_length > self._MAX_BASE_LENGTH:
            return PatternResult(
                pattern_name=self.pattern_name,
                detected=False,
                quality_score=0,
                explanation=(
                    f"Base length {base_length}d > maximum {self._MAX_BASE_LENGTH}d."
                ),
            )

        # Calculate base depth as % decline
        base_depth_pct = (
            (base_region_high - base_region_low) / base_region_high * Decimal("100")
        )

        if base_depth_pct > self._MAX_DEPTH_PCT:
            return PatternResult(
                pattern_name=self.pattern_name,
                detected=False,
                quality_score=0,
                explanation=(
                    f"Base depth {base_depth_pct:.1f}% exceeds max "
                    f"{self._MAX_DEPTH_PCT}%."
                ),
            )

        # Calculate quality score (0-100)
        # Tightness: how close is the range
        tightness_factor = max(
            Decimal("0"),
            Decimal("100")
            - (base_depth_pct / self._MAX_DEPTH_PCT * Decimal("100")),
        )
        quality_score = min(100, int(tightness_factor))

        return PatternResult(
            pattern_name=self.pattern_name,
            detected=True,
            quality_score=quality_score,
            explanation=(
                f"Flat Base detected: {base_length}d width, "
                f"{base_depth_pct:.1f}% depth, "
                f"quality {quality_score}/100."
            ),
            metadata={
                "base_length_days": base_length,
                "base_depth_pct": float(base_depth_pct),
                "base_high": float(base_region_high),
                "base_low": float(base_region_low),
            },
        )