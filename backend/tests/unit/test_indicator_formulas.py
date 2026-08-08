"""Formula-level golden tests for the indicator pipeline (Phase 0.3 / 0.4).

These tests exist because ``_rsi`` and ``_atr`` previously carried docstrings
claiming Wilder's smoothing and "Verified against standard TA definitions" while
implementing a simple rolling mean (Cutler's variant), with no test of either.

Correctness is established two independent ways so the tests cannot be satisfied
by simply mirroring the implementation:

1. **Hand-computed literals.** Small fixtures whose expected RSI/ATR are worked
   out arithmetically in the test docstring, digit by digit.
2. **An independent reference implementation.** ``_reference_wilder`` is a plain
   Python loop written directly from Wilder's published recurrence, sharing no
   code with the vectorized ``ewm``-based production path.

No third-party TA library is available in this environment to cross-check
against, and no published worked example is asserted here: pinning a remembered
constant would be a fabricated verification rather than a real one.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from momentum25.infrastructure.pipelines.indicator_pipeline import (
    _atr,
    _rsi,
    _wilder_smooth,
)

# ── Independent reference implementation (plain loop, no pandas) ─────────────


def _reference_wilder(values: list[float], window: int) -> float:
    """Wilder's smoothed average, written directly from the published recurrence.

    seed = mean(values[:window]); then avg = (avg * (window - 1) + v) / window.
    Deliberately shares no code with the production ``ewm`` implementation.
    """
    avg = sum(values[:window]) / window
    for value in values[window:]:
        avg = (avg * (window - 1) + value) / window
    return avg


def _reference_rsi(closes: list[float], window: int = 14) -> float:
    """RSI from first principles using the loop-based Wilder reference."""
    deltas = [b - a for a, b in zip(closes[:-1], closes[1:], strict=True)]
    gains = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]
    avg_gain = _reference_wilder(gains, window)
    avg_loss = _reference_wilder(losses, window)
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def _reference_atr(
    highs: list[float], lows: list[float], closes: list[float], window: int = 14
) -> float:
    """ATR from first principles using the loop-based Wilder reference."""
    trs = [
        max(h - low_, abs(h - pc), abs(low_ - pc))
        for h, low_, pc in zip(highs[1:], lows[1:], closes[:-1], strict=True)
    ]
    return _reference_wilder(trs, window)


# ── _wilder_smooth ───────────────────────────────────────────────────────────


def test_wilder_smooth_seed_is_simple_mean_of_first_window() -> None:
    """The value at index window-1 is the plain mean of the first `window` inputs.

    Input 1..5, window=5 -> seed = (1+2+3+4+5)/5 = 3.0 exactly.
    """
    result = _wilder_smooth(pd.Series([1.0, 2.0, 3.0, 4.0, 5.0]), 5)
    assert result.iloc[4] == pytest.approx(3.0)
    assert result.iloc[:4].isna().all(), "entries before the seed must be undefined"


def test_wilder_smooth_recurrence_is_hand_computable() -> None:
    """One step past the seed follows (prev*(n-1) + x)/n.

    Input [1,2,3,4,5,10], window=5. seed=3.0 at idx 4.
    idx 5 = (3.0*4 + 10)/5 = 22/5 = 4.4 exactly.
    """
    result = _wilder_smooth(pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 10.0]), 5)
    assert result.iloc[5] == pytest.approx(4.4)


def test_wilder_smooth_differs_materially_from_rolling_mean() -> None:
    """Guards the exact defect being fixed: Wilder's != rolling().mean().

    After a spike, the rolling mean drops the spike entirely once it leaves the
    window; Wilder's retains a decaying tail. If someone reverts to
    rolling(window).mean(), this test fails.
    """
    values = pd.Series([1.0] * 14 + [100.0] + [1.0] * 20)
    wilder = _wilder_smooth(values, 14).iloc[-1]
    rolling = values.rolling(14).mean().iloc[-1]
    assert rolling == pytest.approx(1.0), "spike has fully left the rolling window"
    assert wilder > 2.0, "Wilder's must retain a decaying tail of the spike"


def test_wilder_smooth_matches_independent_loop_reference() -> None:
    """Vectorized ewm path agrees with the plain-loop recurrence."""
    rng = np.random.default_rng(20260808)
    values = [float(v) for v in rng.uniform(1.0, 50.0, size=120)]
    assert _wilder_smooth(pd.Series(values), 14).iloc[-1] == pytest.approx(
        _reference_wilder(values, 14), rel=1e-12
    )


# ── RSI ──────────────────────────────────────────────────────────────────────


def test_rsi_all_gains_is_100() -> None:
    """A monotonically rising series has zero average loss -> RSI 100."""
    assert _rsi(pd.Series([float(i) for i in range(1, 40)]), 14) == pytest.approx(100.0)


def test_rsi_all_losses_is_zero() -> None:
    """A monotonically falling series has zero average gain -> RSI 0."""
    assert _rsi(pd.Series([float(i) for i in range(40, 1, -1)]), 14) == pytest.approx(0.0)


def test_rsi_flat_series_is_50_not_100() -> None:
    """A perfectly flat series has no gains and no losses.

    Reporting 100 (the old code's ``avg_loss == 0`` branch) would label an
    unmoving stock maximally overbought. 50 is the neutral, defensible answer.
    """
    assert _rsi(pd.Series([100.0] * 40), 14) == pytest.approx(50.0)


def test_rsi_alternating_equal_moves_is_near_50() -> None:
    """Equal-sized alternating up/down moves sit near the neutral midpoint.

    Not *exactly* 50: under Wilder's smoothing the most recent delta carries the
    heaviest weight, so a series ending on an up-tick tilts slightly above 50.
    (An equal-weight rolling mean over an even window would give exactly 50 —
    that difference is a property of Wilder's, not a defect.)
    """
    closes = pd.Series([100.0 + (1.0 if i % 2 else 0.0) for i in range(60)])
    rsi = _rsi(closes, 14)
    assert rsi is not None
    assert 47.0 < rsi < 53.0


def test_rsi_hand_computed_two_step_case() -> None:
    """Fully hand-computed RSI, window=3.

    closes = [10, 11, 12, 11, 13]
    deltas  =     +1, +1, -1, +2
    gains   =      1,  1,  0,  2
    losses  =      0,  0,  1,  0

    Wilder seed over the first 3 deltas:
      avg_gain = (1+1+0)/3 = 0.666666...
      avg_loss = (0+0+1)/3 = 0.333333...
    One recurrence step with the 4th delta (gain 2, loss 0), n=3:
      avg_gain = (0.666666... * 2 + 2)/3 = 3.333333.../3 = 1.111111...
      avg_loss = (0.333333... * 2 + 0)/3 = 0.666666.../3 = 0.222222...
      RS  = 1.111111... / 0.222222... = 5.0
      RSI = 100 - 100/6 = 83.333333...
    """
    closes = pd.Series([10.0, 11.0, 12.0, 11.0, 13.0])
    assert _rsi(closes, 3) == pytest.approx(100.0 - 100.0 / 6.0, rel=1e-12)


def test_rsi_seed_step_is_hand_computable_on_wilder_style_series() -> None:
    """A 15-close series exercises the seed only (14 deltas, no recurrence step).

    At the seed, Wilder's average *is* the simple mean of the 14 gains and losses,
    so the expected RSI is computable in closed form without reusing the
    production smoothing path at all.
    """
    closes = [
        44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42,
        45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28,
    ]
    deltas = [b - a for a, b in zip(closes[:-1], closes[1:], strict=True)]
    assert len(deltas) == 14, "this fixture must land exactly on the seed"
    expected_gain = sum(d for d in deltas if d > 0) / 14
    expected_loss = sum(-d for d in deltas if d < 0) / 14
    expected = 100.0 - 100.0 / (1.0 + expected_gain / expected_loss)

    assert _rsi(pd.Series(closes), 14) == pytest.approx(expected, rel=1e-12)


def test_rsi_matches_independent_loop_reference() -> None:
    """Production RSI agrees with the from-first-principles loop implementation."""
    rng = np.random.default_rng(11)
    closes = [100.0]
    for step in rng.normal(0, 2, size=200):
        closes.append(max(1.0, closes[-1] + float(step)))
    assert _rsi(pd.Series(closes), 14) == pytest.approx(_reference_rsi(closes, 14), rel=1e-10)


def test_rsi_insufficient_history_returns_none() -> None:
    """Fewer than window+1 closes cannot form `window` deltas."""
    assert _rsi(pd.Series([1.0] * 14), 14) is None


# ── ATR ──────────────────────────────────────────────────────────────────────


def test_atr_constant_range_equals_that_range() -> None:
    """Bars with identical H/L/C shape have constant TR, so ATR == that TR.

    Each bar: high=102, low=98, close=100 -> TR = max(4, |102-100|, |98-100|) = 4.
    Wilder's average of a constant 4 is 4, at the seed and at every step after.
    """
    frame = pd.DataFrame(
        {"high": [102.0] * 40, "low": [98.0] * 40, "close": [100.0] * 40}
    )
    assert _atr(frame, 14) == pytest.approx(4.0)


def test_atr_uses_gap_not_just_intraday_range() -> None:
    """True range must account for gaps against the previous close.

    Bar n-1 closes at 100; bar n gaps up to low=110, high=112. Intraday range is
    only 2, but |high - prev_close| = 12 is the true range. An implementation
    using high-low alone would report an ATR near 2.
    """
    highs = [102.0] * 20 + [112.0]
    lows = [98.0] * 20 + [110.0]
    closes = [100.0] * 20 + [111.0]
    frame = pd.DataFrame({"high": highs, "low": lows, "close": closes})
    atr = _atr(frame, 14)
    assert atr is not None
    # Seed TR is 4 throughout, then one step absorbing TR=12: (4*13 + 12)/14
    assert atr == pytest.approx((4.0 * 13 + 12.0) / 14, rel=1e-12)


def test_atr_hand_computed_case() -> None:
    """Fully hand-computed ATR, window=3, using 5 bars (4 true ranges).

    bars (h, l, c):
      b0 (10, 8, 9)     -> no prev close, TR undefined, excluded
      b1 (11, 9, 10)    -> TR = max(2, |11-9|, |9-9|)     = 2
      b2 (12, 10, 11)   -> TR = max(2, |12-10|, |10-10|)  = 2
      b3 (14, 11, 13)   -> TR = max(3, |14-11|, |11-11|)  = 3
      b4 (13, 12, 12)   -> TR = max(1, |13-13|, |12-13|)  = 1

    seed = (2 + 2 + 3)/3 = 7/3
    step with TR=1, n=3: (7/3 * 2 + 1)/3 = (14/3 + 3/3)/3 = (17/3)/3 = 17/9
    """
    frame = pd.DataFrame(
        {
            "high": [10.0, 11.0, 12.0, 14.0, 13.0],
            "low": [8.0, 9.0, 10.0, 11.0, 12.0],
            "close": [9.0, 10.0, 11.0, 13.0, 12.0],
        }
    )
    assert _atr(frame, 3) == pytest.approx(17.0 / 9.0, rel=1e-12)


def test_atr_matches_independent_loop_reference() -> None:
    """Production ATR agrees with the from-first-principles loop implementation."""
    rng = np.random.default_rng(7)
    closes = [100.0]
    for step in rng.normal(0, 1.5, size=200):
        closes.append(max(1.0, closes[-1] + float(step)))
    highs = [c + abs(float(rng.uniform(0, 2))) for c in closes]
    lows = [c - abs(float(rng.uniform(0, 2))) for c in closes]
    frame = pd.DataFrame({"high": highs, "low": lows, "close": closes})
    assert _atr(frame, 14) == pytest.approx(
        _reference_atr(highs, lows, closes, 14), rel=1e-10
    )


def test_atr_differs_from_old_rolling_mean_implementation() -> None:
    """Regression guard for the exact defect fixed in Phase 0.4.

    Reproduces the previous rolling-mean ATR and asserts the new value differs
    materially on a series with a volatility spike.
    """
    highs = [102.0] * 14 + [140.0] + [102.0] * 20
    lows = [98.0] * 14 + [60.0] + [98.0] * 20
    closes = [100.0] * 35
    frame = pd.DataFrame({"high": highs, "low": lows, "close": closes})

    prev_close = np.roll(np.array(closes), 1)
    prev_close[0] = closes[0]
    old_tr = np.maximum(
        np.array(highs) - np.array(lows),
        np.maximum(
            np.abs(np.array(highs) - prev_close), np.abs(np.array(lows) - prev_close)
        ),
    )
    old_atr = float(pd.Series(old_tr).rolling(14).mean().iloc[-1])
    new_atr = _atr(frame, 14)

    assert new_atr is not None
    assert old_atr == pytest.approx(4.0), "old rolling mean forgets the spike entirely"
    assert new_atr > 5.0, "Wilder's must still carry the spike's decaying tail"


def test_atr_insufficient_history_returns_none() -> None:
    """Fewer than window+1 bars cannot form `window` true ranges."""
    frame = pd.DataFrame(
        {"high": [102.0] * 14, "low": [98.0] * 14, "close": [100.0] * 14}
    )
    assert _atr(frame, 14) is None
