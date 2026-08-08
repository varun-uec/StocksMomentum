"""Hand-computed golden tests for the Phase 6.3/6.4 indicator formulas.

Every expectation below is worked out by hand from the published definition, not
captured from the implementation's own output -- a snapshot test would happily
lock in a wrong formula.
"""

from __future__ import annotations

import pandas as pd
import pytest

from momentum25.infrastructure.pipelines.indicator_pipeline import (
    _cci,
    _pct_from,
    _roc,
    _stochastic,
    _williams_r,
)


def _frame(highs: list[float], lows: list[float], closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"high": highs, "low": lows, "close": closes})


# ── 6.3 distance from moving average ──────────────────────────────────────


def test_pct_from_moving_average_is_signed() -> None:
    assert _pct_from(110.0, 100.0) == pytest.approx(10.0)
    assert _pct_from(90.0, 100.0) == pytest.approx(-10.0)


def test_pct_from_missing_or_zero_average_is_none() -> None:
    assert _pct_from(110.0, None) is None
    assert _pct_from(110.0, 0.0) is None


# ── 6.4 Stochastic ────────────────────────────────────────────────────────


def test_stochastic_k_is_position_within_the_14_bar_range() -> None:
    # 16 bars so %D (a 3-period mean of %K) is defined.
    highs = [110.0] * 16
    lows = [100.0] * 16
    closes = [105.0] * 16
    # Final three closes: 102, 104, 107.5 -> %K = 20, 40, 75
    closes[-3:] = [102.0, 104.0, 107.5]

    k, d = _stochastic(_frame(highs, lows, closes), window=14, smooth=3)

    assert k == pytest.approx(75.0)  # (107.5 - 100) / (110 - 100) * 100
    assert d == pytest.approx((20.0 + 40.0 + 75.0) / 3)


def test_stochastic_on_a_zero_width_range_is_none_not_a_substituted_midpoint() -> None:
    flat = [100.0] * 16
    k, d = _stochastic(_frame(flat, flat, flat), window=14, smooth=3)
    assert k is None
    assert d is None


def test_stochastic_needs_window_plus_smoothing_bars() -> None:
    highs = [110.0] * 15
    k, d = _stochastic(_frame(highs, [100.0] * 15, [105.0] * 15), window=14, smooth=3)
    assert k is not None  # %K only needs 14
    assert d is None  # %D needs 16


# ── 6.4 Williams %R ───────────────────────────────────────────────────────


def test_williams_r_is_stochastic_k_minus_100() -> None:
    highs = [110.0] * 16
    lows = [100.0] * 16
    closes = [105.0] * 15 + [107.5]

    r = _williams_r(_frame(highs, lows, closes), window=14)
    k, _ = _stochastic(_frame(highs, lows, closes), window=14, smooth=3)

    assert r == pytest.approx(-25.0)  # -100 * (110 - 107.5) / 10
    assert k is not None
    assert r == pytest.approx(k - 100.0)


def test_williams_r_at_the_range_extremes() -> None:
    highs, lows = [110.0] * 14, [100.0] * 14
    assert _williams_r(_frame(highs, lows, [105.0] * 13 + [110.0]), 14) == pytest.approx(0.0)
    assert _williams_r(_frame(highs, lows, [105.0] * 13 + [100.0]), 14) == pytest.approx(-100.0)


# ── 6.4 CCI ───────────────────────────────────────────────────────────────


def test_cci_uses_mean_absolute_deviation_not_standard_deviation() -> None:
    # 20 typical prices: nineteen at 100, final at 110.
    #   mean TP        = (19*100 + 110) / 20 = 100.5
    #   MAD            = (19*0.5 + 9.5) / 20 = 0.95
    #   CCI            = (110 - 100.5) / (0.015 * 0.95) = 666.666...
    values = [100.0] * 19 + [110.0]
    df = _frame(values, values, values)

    assert _cci(df, window=20) == pytest.approx(9.5 / (0.015 * 0.95))


def test_cci_on_a_flat_window_is_none() -> None:
    flat = [100.0] * 20
    assert _cci(_frame(flat, flat, flat), window=20) is None


def test_cci_needs_a_full_window() -> None:
    values = [100.0] * 19
    assert _cci(_frame(values, values, values), window=20) is None


# ── 6.4 ROC ───────────────────────────────────────────────────────────────


def test_roc_is_percent_change_over_the_window() -> None:
    closes = pd.Series([100.0] + [0.0] * 11 + [125.0])  # 13 bars: index 0 is 12 back
    assert _roc(closes, window=12) == pytest.approx(25.0)


def test_roc_needs_window_plus_one_bars() -> None:
    assert _roc(pd.Series([100.0] * 12), window=12) is None


def test_roc_on_a_zero_base_is_none() -> None:
    closes = pd.Series([0.0] + [1.0] * 12)
    assert _roc(closes, window=12) is None
