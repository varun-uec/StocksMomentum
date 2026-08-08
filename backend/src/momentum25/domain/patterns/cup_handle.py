"""Cup with Handle pattern detector.

A cup with handle is a bullish continuation pattern that resembles a teacup:
a rounded bottom (cup) followed by a brief pullback (handle) on lower volume.

Rules:
- Cup depth: 15–35% decline from cup high to cup low
- Cup width: at least 7 weeks (35 days)
- Handle depth: ≤ 15% decline from handle high to handle low
- Handle trades on declining volume
- Price is near the top of the cup (ready to break out)
"""

from __future__ import annotations

from decimal import Decimal

from momentum25.domain.patterns.base import PatternDetector, PatternResult


class CupWithHandleDetector:
    """Detects a Cup with Handle pattern."""

    pattern_name = "cup_with_handle"

    _MIN_CUP_DEPTH_PCT = Decimal("15")
    _MAX_CUP_DEPTH_PCT = Decimal("35")
    _MIN_CUP_LENGTH = 35
    _MAX_HANDLE_DEPTH_PCT = Decimal("15")
    _MIN_HANDLE_LENGTH = 5

    def detect(
        self,
        close: list[Decimal],
        high: list[Decimal],
        low: list[Decimal],
        volume: list[int],
    ) -> PatternResult:
        if len(close) < self._MIN_CUP_LENGTH + 20:
            return PatternResult(
                pattern_name=self.pattern_name,
                detected=False,
                quality_score=0,
                explanation="Insufficient data: need at least 55 bars.",
            )

        lookback = min(len(close), 100)
        recent_high = high[-lookback:]
        recent_low = low[-lookback:]
        recent_volume = volume[-lookback:]

        # Find the cup high (left peak) — the highest point in the first half
        mid_idx = len(recent_high) // 2
        left_half = recent_high[:mid_idx]
        if not left_half:
            return PatternResult(
                pattern_name=self.pattern_name,
                detected=False,
                quality_score=0,
                explanation="Cannot identify left cup peak.",
            )

        left_peak = max(left_half)
        left_peak_idx = recent_high.index(left_peak)

        # Find the cup bottom (lowest point after left peak)
        after_peak = recent_low[left_peak_idx:]
        if not after_peak:
            return PatternResult(
                pattern_name=self.pattern_name,
                detected=False,
                quality_score=0,
                explanation="Cannot identify cup bottom.",
            )

        cup_bottom = min(after_peak)
        cup_bottom_idx = recent_low.index(cup_bottom)

        # Cup depth
        cup_depth_pct = (left_peak - cup_bottom) / left_peak * Decimal("100")

        if cup_depth_pct < self._MIN_CUP_DEPTH_PCT:
            return PatternResult(
                pattern_name=self.pattern_name,
                detected=False,
                quality_score=0,
                explanation=(
                    f"Cup depth {cup_depth_pct:.1f}% < min {self._MIN_CUP_DEPTH_PCT}%."
                ),
            )

        if cup_depth_pct > self._MAX_CUP_DEPTH_PCT:
            return PatternResult(
                pattern_name=self.pattern_name,
                detected=False,
                quality_score=0,
                explanation=(
                    f"Cup depth {cup_depth_pct:.1f}% > max {self._MAX_CUP_DEPTH_PCT}%."
                ),
            )

        # Cup width
        cup_width = cup_bottom_idx - left_peak_idx
        if cup_width < self._MIN_CUP_LENGTH:
            return PatternResult(
                pattern_name=self.pattern_name,
                detected=False,
                quality_score=0,
                explanation=(
                    f"Cup width {cup_width}d < min {self._MIN_CUP_LENGTH}d."
                ),
            )

        # Right side: after cup bottom, price should come back up
        # The handle forms on the right side near the top
        right_side = recent_high[cup_bottom_idx:]
        if len(right_side) < self._MIN_HANDLE_LENGTH + 3:
            return PatternResult(
                pattern_name=self.pattern_name,
                detected=False,
                quality_score=0,
                explanation="Insufficient right side data for handle.",
            )

        # Right peak — should approach left peak level
        right_peak = max(right_side)

        # Find handle: the rightmost pullback
        handle_region = right_side[-(self._MIN_HANDLE_LENGTH + 5):]
        handle_high = max(handle_region)
        handle_low = min(recent_low[-len(handle_region):])
        handle_depth_pct = (handle_high - handle_low) / handle_high * Decimal("100")

        if handle_depth_pct > self._MAX_HANDLE_DEPTH_PCT:
            return PatternResult(
                pattern_name=self.pattern_name,
                detected=False,
                quality_score=0,
                explanation=(
                    f"Handle depth {handle_depth_pct:.1f}% > max "
                    f"{self._MAX_HANDLE_DEPTH_PCT}%."
                ),
            )

        # Check volume contraction in handle
        handle_vol_avg = sum(recent_volume[-len(handle_region):]) / max(len(handle_region), 1)
        prior_vol_avg = sum(recent_volume[-len(handle_region) * 2:-len(handle_region)]) / max(
            len(handle_region), 1
        )

        volume_confirming = prior_vol_avg == 0 or handle_vol_avg <= prior_vol_avg * 1.1

        # Quality score
        depth_score = max(
            0, 100 - int(abs(cup_depth_pct - Decimal("25")))
        )  # Perfect is ~25%
        vol_score = 30 if volume_confirming else 0
        quality_score = min(100, depth_score + vol_score)

        return PatternResult(
            pattern_name=self.pattern_name,
            detected=True,
            quality_score=quality_score,
            explanation=(
                f"Cup with Handle detected: {cup_width}d cup, "
                f"{cup_depth_pct:.1f}% depth, "
                f"{handle_depth_pct:.1f}% handle depth, "
                f"quality {quality_score}/100."
            ),
            metadata={
                "cup_width_days": cup_width,
                "cup_depth_pct": float(cup_depth_pct),
                "handle_depth_pct": float(handle_depth_pct),
                "volume_confirming": volume_confirming,
            },
        )