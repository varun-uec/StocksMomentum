"""The ``IndicatorSet`` value object — computed technical indicators for one security.

All fields are ``None`` when there is insufficient history; such a security is
flagged ineligible rather than causing an error (NFR determinism contract).
Values are quantized to ``Decimal`` at the persistence boundary (ADR-009).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class IndicatorSet:
    """Indicator values for a single security as of a given date."""

    as_of: date
    sma50: Decimal | None = None
    sma150: Decimal | None = None
    sma200: Decimal | None = None
    ema10: Decimal | None = None
    ema21: Decimal | None = None
    rsi14: Decimal | None = None
    atr14: Decimal | None = None
    adr_pct: Decimal | None = None
    high_52w: Decimal | None = None
    low_52w: Decimal | None = None
    pct_above_low_52w: Decimal | None = None
    pct_below_high_52w: Decimal | None = None
    sma200_slope_pct: Decimal | None = None
    rs_rating: int | None = None
    rs_percentile: Decimal | None = None
    rs_line_slope: Decimal | None = None
    avg_volume50: Decimal | None = None
    rel_volume: Decimal | None = None

    # ── Trend strength (Phase 2.1) ───────────────────────────────────────
    adx14: Decimal | None = None
    plus_di14: Decimal | None = None
    minus_di14: Decimal | None = None

    # ── MACD(12,26,9) (Phase 2.2) ────────────────────────────────────────
    macd_line: Decimal | None = None
    macd_signal: Decimal | None = None
    macd_histogram: Decimal | None = None

    # ── Swing pivot support/resistance (Phase 2.3) ───────────────────────
    # Nearest confirmed N-bar fractal swing high/low around the latest close
    # -- see indicator_pipeline._swing_levels. Exposed as data (not just used
    # internally by the breakout engine's fixed 20-day range) as a
    # prerequisite for Phase 3 target/stop-loss logic.
    swing_resistance: Decimal | None = None
    swing_support: Decimal | None = None

    # ── Multi-timeframe RS fields ────────────────────────────────────────
    rs_raw_1m: Decimal | None = None  # 1-month (22d) raw return
    rs_raw_3m: Decimal | None = None  # 3-month (63d) raw return
    rs_raw_6m: Decimal | None = None  # 6-month (126d) raw return
    rs_raw_12m: Decimal | None = None  # 12-month (252d) raw return
    rs_line_1m_slope: Decimal | None = None  # RS line slope over 22d
    rs_line_3m_slope: Decimal | None = None  # RS line slope over 63d

    # ── Historical RS tracking ───────────────────────────────────────────
    rs_rating_1m_ago: int | None = None
    rs_rating_3m_ago: int | None = None
    rs_rating_trend: str | None = None  # "improving", "declining", "stable"

    # ── Sector/industry RS ───────────────────────────────────────────────
    sector_rs_percentile: Decimal | None = None
    industry_rs_percentile: Decimal | None = None