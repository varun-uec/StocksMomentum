"""Volatility Contraction Pattern (VCP) detector.

The VCP is Mark Minervini's signature pattern: the stock contracts in volatility
over several contractions, each with smaller price ranges and declining volume.

Rules:
- At least 3 contractions (tightening price ranges)
- Each contraction has lower absolute range (high-low) than the previous
- Volume declining across contractions
- Overall pattern depth ≤ 35%
"""

from __future__ import annotations

from decimal import Decimal

from momentum25.domain.patterns.base import PatternDetector, PatternResult


class VCPDetector:
    """Detects a Volatility Contraction Pattern (VCP)."""

    pattern_name = "vcp"

    _MIN_CONTRACTIONS = 3
    _MAX_DEPTH_PCT = Decimal("35")
    _LOOKBACK_BARS = 80

    def detect(
        self,
        close: list[Decimal],
        high: list[Decimal],
        low: list[Decimal],
        volume: list[int],
    ) -> PatternResult:
        if len(close) < self._LOOKBACK_BARS:
            return PatternResult(
                pattern_name=self.pattern_name,
                detected=False,
                quality_score=0,
                explanation=(
                    f"Insufficient data: need {self._LOOKBACK_BARS} bars, "
                    f"got {len(close)}."
                ),
            )

        lookback = min(len(close), self._LOOKBACK_BARS)
        recent_high = [float(h) for h in high[-lookback:]]
        recent_low = [float(l) for l in low[-lookback:]]
        recent_volume = list(volume[-lookback:])

        # Compute daily ranges (high - low) / close
        ranges = [
            (recent_high[i] - recent_low[i]) / max(float(close[-lookback:][i]), 0.01)
            for i in range(len(recent_high))
        ]

        # Find contractions by splitting into segments and measuring range
        num_segments = min(8, lookback // 10)
        segment_size = lookback // num_segments

        contraction_ranges: list[float] = []
        contraction_volumes: list[float] = []

        for i in range(num_segments):
            start = i * segment_size
            end = start + segment_size
            seg_ranges = ranges[start:end]
            seg_vols = recent_volume[start:end]
            if seg_ranges:
                contraction_ranges.append(max(seg_ranges))
                contraction_volumes.append(sum(seg_vols) / len(seg_vols))

        # Check for contracting ranges (each should be smaller or equal)
        contractions = 0
        for i in range(1, len(contraction_ranges)):
            if contraction_ranges[i] <= contraction_ranges[i - 1] * 1.05:
                contractions += 1

        if contractions < self._MIN_CONTRACTIONS:
            return PatternResult(
                pattern_name=self.pattern_name,
                detected=False,
                quality_score=0,
                explanation=(
                    f"Found {contractions} contractions, "
                    f"need ≥ {self._MIN_CONTRACTIONS}."
                ),
            )

        # Check volume declining
        vol_declining = sum(
            1 for i in range(1, len(contraction_volumes))
            if contraction_volumes[i] <= contraction_volumes[i - 1]
        )

        # Overall depth check
        overall_high = max(recent_high)
        overall_low = min(recent_low)
        depth_pct = float(overall_high - overall_low) / overall_high * 100

        if depth_pct > float(self._MAX_DEPTH_PCT):
            return PatternResult(
                pattern_name=self.pattern_name,
                detected=False,
                quality_score=0,
                explanation=f"Pattern depth {depth_pct:.1f}% > max 35%.",
            )

        # Quality score
        contraction_score = min(50, contractions * 15)
        vol_score = min(30, vol_declining * 10)
        depth_score = max(0, 20 - int(depth_pct / 5))
        quality_score = min(100, contraction_score + vol_score + depth_score)

        return PatternResult(
            pattern_name=self.pattern_name,
            detected=True,
            quality_score=quality_score,
            explanation=(
                f"VCP detected: {contractions} contractions, "
                f"{vol_declining} volume declines, "
                f"{depth_pct:.1f}% depth, quality {quality_score}/100."
            ),
            metadata={
                "contractions": contractions,
                "vol_declining_segments": vol_declining,
                "depth_pct": depth_pct,
            },
        )