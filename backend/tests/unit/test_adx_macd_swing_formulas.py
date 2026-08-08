"""Formula-level golden tests for ADX, MACD, and swing pivots (Phase 2.1/2.2/2.3).

Same verification convention as ``test_indicator_formulas.py`` (Phase 0): a
hand-computed case worked out digit-by-digit in the docstring, plus an
independent from-first-principles loop implementation sharing no code with the
vectorized production path, for the cases where hand computation over enough
bars to reach a stable value is impractical.

Writing the independent ADX reference caught a real bug in the first version of
``_adx``: naively passing the DX series (which inherits leading NaNs from the
first Wilder-smoothing pass over +DM/-DM/TR) straight into ``_wilder_smooth``
seeds the second pass on a single real value instead of averaging the first
``window`` real DX readings the way Wilder's published method requires. See the
comment in ``_adx`` for the fix (drop the leading NaNs before the second pass).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from momentum25.infrastructure.pipelines.indicator_pipeline import (
    _adx,
    _macd,
    _swing_levels,
)

# ── Independent reference implementation (plain loop, no pandas) ─────────────


def _reference_wilder_seq(values: list[float], window: int) -> list[float]:
    """Wilder's smoothed sequence (not just the final value), loop-based."""
    avg = sum(values[:window]) / window
    out = [avg]
    for value in values[window:]:
        avg = (avg * (window - 1) + value) / window
        out.append(avg)
    return out


def _reference_adx(
    highs: list[float], lows: list[float], closes: list[float], window: int = 14
) -> tuple[float, float, float]:
    """ADX/+DI/-DI from first principles using the loop-based Wilder reference."""
    n = len(highs)
    up = [highs[i] - highs[i - 1] for i in range(1, n)]
    down = [lows[i - 1] - lows[i] for i in range(1, n)]
    plus_dm = [u if (u > d and u > 0) else 0.0 for u, d in zip(up, down, strict=True)]
    minus_dm = [d if (d > u and d > 0) else 0.0 for u, d in zip(up, down, strict=True)]
    trs = [
        max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        for i in range(1, n)
    ]
    smoothed_plus = _reference_wilder_seq(plus_dm, window)
    smoothed_minus = _reference_wilder_seq(minus_dm, window)
    smoothed_tr = _reference_wilder_seq(trs, window)

    dx = []
    for a, b, c in zip(smoothed_plus, smoothed_minus, smoothed_tr, strict=True):
        pdi, mdi = 100 * a / c, 100 * b / c
        s = pdi + mdi
        dx.append(100 * abs(pdi - mdi) / s if s != 0 else 0.0)

    adx = _reference_wilder_seq(dx, window)[-1]
    plus_di = 100 * smoothed_plus[-1] / smoothed_tr[-1]
    minus_di = 100 * smoothed_minus[-1] / smoothed_tr[-1]
    return adx, plus_di, minus_di


def _reference_ema_seq(values: list[float], span: int) -> list[float]:
    """EMA sequence matching pandas ``ewm(span=..., adjust=False)``: seeded with values[0]."""
    k = 2.0 / (span + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def _reference_macd(
    closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[float, float, float]:
    """MACD from first principles using the loop-based EMA reference."""
    ema_fast = _reference_ema_seq(closes, fast)
    ema_slow = _reference_ema_seq(closes, slow)
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow, strict=True)]
    signal_line = _reference_ema_seq(macd_line, signal)
    return macd_line[-1], signal_line[-1], macd_line[-1] - signal_line[-1]


# ── ADX / +DI / -DI ────────────────────────────────────────────────────────


def test_adx_hand_computed_seed_only_case() -> None:
    """Fully hand-computed ADX/+DI/-DI, window=3, 6 bars (5 DM/TR readings).

    bars (h, l, c): (10,8,9) (12,9,11) (11,9,10) (14,10,13) (13,11,12) (16,12,15)

    up_move = h[i]-h[i-1]:    2, -1,  3, -1,  3
    down_move = l[i-1]-l[i]: -1,  0, -1, -1, -1
    +DM (up>down and up>0):   2,  0,  3,  0,  3
    -DM (down>up and down>0): 0,  0,  0,  0,  0   -- always zero in this fixture
    TR:                       3,  2,  4,  2,  4

    Wilder seed (mean of first 3): +DM=5/3, TR=3, -DM=0.
    Two recurrence steps (n=3) bring +DM to 47/27, TR to 28/9 at the last reading.
    +DI = 100*(47/27)/(28/9) = 100*47/84 = 55.952380952...
    -DI = 0 (smoothed -DM is 0 throughout)
    DX at every defined step = 100*|+DI-0|/(+DI+0) = 100 (whenever +DI != 0),
    so DX is exactly 100 at all 3 valid readings -> ADX seed = mean(100,100,100) = 100.0.
    """
    df = pd.DataFrame(
        {
            "high": [10.0, 12.0, 11.0, 14.0, 13.0, 16.0],
            "low": [8.0, 9.0, 9.0, 10.0, 11.0, 12.0],
            "close": [9.0, 11.0, 10.0, 13.0, 12.0, 15.0],
        }
    )
    adx, plus_di, minus_di = _adx(df, 3)
    assert adx == pytest.approx(100.0, rel=1e-12)
    assert plus_di == pytest.approx(100.0 * 47.0 / 84.0, rel=1e-12)
    assert minus_di == pytest.approx(0.0, abs=1e-12)


def test_adx_is_none_when_dx_history_shorter_than_window() -> None:
    """+DI/-DI can be defined before ADX is -- ADX needs a second full smoothing pass.

    5 bars (4 DM/TR readings) with window=3 gives only 2 valid DX readings, short
    of the 3 needed to seed ADX's own Wilder average. +DI/-DI are still defined
    (they only need the first smoothing pass). This is the exact bug this test
    file's docstring describes: naively smoothing the NaN-prefixed DX series
    would have produced a spurious ADX value here instead of ``None``.
    """
    df = pd.DataFrame(
        {
            "high": [10.0, 12.0, 11.0, 13.0, 12.0],
            "low": [8.0, 9.0, 9.0, 10.0, 11.0],
            "close": [9.0, 11.0, 10.0, 12.0, 11.0],
        }
    )
    adx, plus_di, minus_di = _adx(df, 3)
    assert adx is None
    assert plus_di is not None
    assert minus_di is not None


def test_adx_matches_independent_loop_reference() -> None:
    """Production ADX/+DI/-DI agree with the from-first-principles loop implementation."""
    rng = np.random.default_rng(42)
    closes = [100.0]
    for step in rng.normal(0.2, 1.5, size=80):
        closes.append(max(1.0, closes[-1] + float(step)))
    highs = [c + abs(float(rng.uniform(0, 1.5))) for c in closes]
    lows = [c - abs(float(rng.uniform(0, 1.5))) for c in closes]
    frame = pd.DataFrame({"high": highs, "low": lows, "close": closes})

    adx, plus_di, minus_di = _adx(frame, 14)
    ref_adx, ref_plus, ref_minus = _reference_adx(highs, lows, closes, 14)

    assert adx == pytest.approx(ref_adx, rel=1e-9)
    assert plus_di == pytest.approx(ref_plus, rel=1e-9)
    assert minus_di == pytest.approx(ref_minus, rel=1e-9)


def test_adx_insufficient_history_returns_all_none() -> None:
    """Fewer than window+1 bars cannot form even one true range."""
    frame = pd.DataFrame({"high": [102.0] * 14, "low": [98.0] * 14, "close": [100.0] * 14})
    assert _adx(frame, 14) == (None, None, None)


def test_adx_strong_trend_scores_higher_than_choppy_series() -> None:
    """Directional sanity check: a clean trend has higher ADX than a sideways chop.

    Not a hand-computed value -- just the qualitative property ADX exists to
    capture (trend *strength* regardless of direction).
    """
    trend_closes = [100.0 + i * 1.5 for i in range(60)]
    trend_df = pd.DataFrame({
        "high": [c + 1 for c in trend_closes],
        "low": [c - 1 for c in trend_closes],
        "close": trend_closes,
    })
    choppy_closes = [100.0 + (2.0 if i % 2 == 0 else -2.0) for i in range(60)]
    choppy_df = pd.DataFrame({
        "high": [c + 1 for c in choppy_closes],
        "low": [c - 1 for c in choppy_closes],
        "close": choppy_closes,
    })

    trend_adx, _, _ = _adx(trend_df, 14)
    choppy_adx, _, _ = _adx(choppy_df, 14)
    assert trend_adx is not None
    assert choppy_adx is not None
    assert trend_adx > choppy_adx


# ── MACD ─────────────────────────────────────────────────────────────────────


def test_macd_flat_series_is_exactly_zero() -> None:
    """A constant price has EMA_fast == EMA_slow == price at every point -> MACD 0."""
    closes = pd.Series([100.0] * 40)
    macd_line, signal, histogram = _macd(closes, fast=12, slow=26, signal=9)
    assert macd_line == pytest.approx(0.0, abs=1e-9)
    assert signal == pytest.approx(0.0, abs=1e-9)
    assert histogram == pytest.approx(0.0, abs=1e-9)


def test_macd_matches_independent_loop_reference() -> None:
    """Production MACD agrees with the from-first-principles EMA loop implementation."""
    rng = np.random.default_rng(99)
    closes = [100.0]
    for step in rng.normal(0, 1.2, size=80):
        closes.append(max(1.0, closes[-1] + float(step)))

    macd_line, signal, histogram = _macd(pd.Series(closes))
    ref_line, ref_signal, ref_hist = _reference_macd(closes)

    assert macd_line == pytest.approx(ref_line, rel=1e-10)
    assert signal == pytest.approx(ref_signal, rel=1e-10)
    assert histogram == pytest.approx(ref_hist, rel=1e-10)


def test_macd_insufficient_history_returns_none() -> None:
    """Fewer than slow+signal closes cannot form a fully-defined signal line."""
    assert _macd(pd.Series([100.0] * 30)) == (None, None, None)


def test_macd_histogram_equals_line_minus_signal() -> None:
    """Internal consistency: histogram is always exactly macd_line - signal_line."""
    rng = np.random.default_rng(3)
    closes = [100.0]
    for step in rng.normal(0, 1.0, size=60):
        closes.append(max(1.0, closes[-1] + float(step)))
    macd_line, signal, histogram = _macd(pd.Series(closes))
    assert macd_line is not None and signal is not None and histogram is not None
    assert histogram == pytest.approx(macd_line - signal, rel=1e-12)


# ── Swing pivot support/resistance ───────────────────────────────────────────


def test_swing_levels_hand_constructed_pivots() -> None:
    """Confirmed fractal highs/lows are found; the nearest above/below close wins.

    left=right=2. Highs carry three confirmable local peaks (15 @ idx2,
    20 @ idx6, 12 @ idx9); lows carry one confirmable trough (3 @ idx5). The
    final close is 11, so: nearest resistance = min(15, 20, 12) = 12 (all lie
    above 11), nearest support = 3 (the only low below 11).
    """
    highs = [10, 10, 15, 10, 10, 10, 20, 10, 10, 12, 10, 10, 10]
    lows = [8, 8, 8, 8, 8, 3, 8, 8, 8, 8, 8, 8, 8]
    closes = [9] * 12 + [11]
    df = pd.DataFrame(
        {
            "high": [float(h) for h in highs],
            "low": [float(lo) for lo in lows],
            "close": [float(c) for c in closes],
        }
    )
    resistance, support = _swing_levels(df, left=2, right=2)
    assert resistance == pytest.approx(12.0)
    assert support == pytest.approx(3.0)


def test_swing_levels_excludes_unconfirmed_recent_pivots() -> None:
    """A pivot needs `right` bars after it to be confirmed -- recent spikes don't count.

    A huge high sits two bars from the end, which is exactly where `right=2`
    cannot confirm it (no bars remain after it within the window). It must be
    excluded even though it is, by far, the highest value in the series.
    """
    highs = [10.0] * 10 + [50.0, 10.0]
    lows = [8.0] * 12
    closes = [9.0] * 12
    df = pd.DataFrame({"high": highs, "low": lows, "close": closes})
    resistance, support = _swing_levels(df, left=2, right=2)
    assert resistance is None
    assert support is None


def test_swing_levels_insufficient_bars_returns_none() -> None:
    """Fewer than left + right + 1 bars cannot confirm any pivot at all."""
    df = pd.DataFrame({"high": [10.0] * 4, "low": [8.0] * 4, "close": [9.0] * 4})
    assert _swing_levels(df, left=2, right=2) == (None, None)


def test_swing_levels_no_level_on_one_side_is_none_not_an_error() -> None:
    """A monotonically rising series has no confirmed high above the (highest) close."""
    n = 20
    closes = [100.0 + i for i in range(n)]
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    df = pd.DataFrame({"high": highs, "low": lows, "close": closes})
    resistance, support = _swing_levels(df, left=3, right=3)
    assert resistance is None  # nothing in the series exceeds the latest (highest) close
