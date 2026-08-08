"""Production-grade technical indicator pipeline.

Fetches historical OHLCV data from the database and computes a fully typed
:class:`IndicatorSet` using vectorized pandas/numpy calculations. Handles
insufficient history gracefully by returning ``None`` for unavailable metrics.

All indicator formulas per IMPLEMENTATION_SPEC.md §8 with verified correctness.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.value_objects.indicators import IndicatorSet
from momentum25.infrastructure.logging.setup import get_logger
from momentum25.infrastructure.persistence.models import (
    LegacyOHLCVDailyModel,
    OHLCVDailyModel,
)

_logger = get_logger("indicator_pipeline")

# Default indicator windows (the minervini_trend_template 1-Year strategy).
# A strategy's own ``indicators`` config block overrides these per Momentum
# Horizon (ADR-005: strategy-as-config); these are only the fallback when a
# key is absent, so historical/default behavior is unchanged.
_DEFAULT_SMA_WINDOWS = (50, 150, 200)
_DEFAULT_SLOPE_WINDOW = 22
_DEFAULT_HIGH_LOW_WINDOW = 252
_DEFAULT_AVG_VOLUME_WINDOW = 50
_MIN_BARS_BUFFER = 25

# Fixed precision for the indicator egress boundary (ADR-009 determinism contract).
_QUANT = Decimal("0.0001")

# Indicator-formula revision. ``config_hash`` covers the *strategy* (which rules,
# weights, thresholds) but not the *formulas* those rules consume, so before this
# a silent formula change made new runs quietly incomparable to stored ones while
# leaving config_hash identical. Stamped into ``ScreeningRun.stats`` by both the
# live and historical orchestrators; runs may only be compared to each other when
# their ``indicator_version`` matches as well as their ``config_hash``.
#
# Bump on ANY change to a computed indicator value. History:
#   1 — original formulas.
#   2 — Phase 0.3/0.4: RSI and ATR corrected from a rolling mean (Cutler's) to
#       Wilder's smoothing. Measured effect on random walks: RSI shifts a mean of
#       6.7 points (max 21.8); ATR shifts a mean of 3.8% (max 14.4%). Runs stamped
#       1 are NOT comparable to runs stamped 2.
#
# NOT bumped for Phase 6.3/6.4 (pct_from_sma50/200, Stochastic, Williams %R, CCI,
# ROC): those are purely additive display fields. No pre-existing indicator value
# changes, and no rule consumes them, so runs stamped 2 before and after remain
# byte-for-byte comparable. Bump only when an existing value moves.
INDICATOR_VERSION = 2


def _quantize(value: float | None) -> Decimal | None:
    """Cast a float metric to a fixed-precision ``Decimal`` (or ``None``).

    Quantizing through the string representation avoids binary-float artifacts,
    guaranteeing identical Decimals for identical inputs across runs.
    """
    if value is None:
        return None
    return Decimal(f"{value:.4f}").quantize(_QUANT)


def _sma(series: pd.Series, window: int) -> float | None:
    """Simple Moving Average over trailing ``window`` periods."""
    if len(series) < window:
        return None
    val = series.rolling(window=window).mean().iloc[-1]
    return float(val) if not pd.isna(val) else None


def _ema(series: pd.Series, span: int) -> pd.Series:
    """Exponential Moving Average using pandas ewm (span semantics).

    EMA_t = price_t * k + EMA_{t-1} * (1 - k), k = 2 / (span + 1). Seeded with the
    series' first value (``ewm(adjust=False)``'s actual behaviour -- not an
    SMA-of-first-``span``-values seed, a common but different convention some other
    EMA implementations use). Values before the span-th are therefore not a "true"
    EMA yet; callers requiring the fully warmed-up value should have at least
    ``span`` bars of buffer beyond their minimum, as the SMA-window callers already do.
    """
    return series.ewm(span=span, adjust=False).mean()


def _wilder_smooth(values: pd.Series, window: int) -> pd.Series:
    """Wilder's smoothing (modified moving average) of ``values``.

    Wilder's recurrence is ``avg_t = (avg_{t-1} * (window - 1) + value_t) / window``,
    seeded with the simple mean of the first ``window`` values. That recurrence is
    exactly an EWM with ``alpha = 1 / window`` and ``adjust=False``, so it is
    expressed here as one vectorized ``ewm`` call over a series whose first
    ``window - 1`` entries are masked out and whose ``window``-th entry carries the
    seed — pandas begins the recursion at the first non-NaN value.

    This is *not* interchangeable with ``rolling(window).mean()``: the rolling mean
    (Cutler's variant) weights the trailing ``window`` observations equally and
    forgets everything older, while Wilder's retains an exponentially-decaying tail
    of the full history. The two do not converge, and every published RSI/ATR
    threshold (RSI 30/70, ATR-multiple stops) is calibrated against Wilder's.
    """
    if len(values) < window:
        return pd.Series([float("nan")] * len(values), index=values.index, dtype="float64")
    seeded = values.astype("float64").copy()
    seeded.iloc[: window - 1] = np.nan
    seeded.iloc[window - 1] = float(values.iloc[:window].mean())
    return seeded.ewm(alpha=1.0 / window, adjust=False, ignore_na=False).mean()


def _rsi(series: pd.Series, window: int = 14) -> float | None:
    """Wilder's RSI over ``window`` periods.

    ``RSI = 100 - 100 / (1 + RS)`` where ``RS = avg_gain / avg_loss`` and both
    averages use Wilder's smoothing (:func:`_wilder_smooth`), seeded from the first
    ``window`` price changes. Covered by hand-computed golden tests in
    ``tests/unit/test_indicator_formulas.py``.
    """
    if len(series) < window + 1:
        return None
    deltas = series.astype("float64").diff().dropna()
    if len(deltas) < window:
        return None
    gains = deltas.clip(lower=0.0)
    losses = (-deltas).clip(lower=0.0)
    avg_gain = _wilder_smooth(gains, window).iloc[-1]
    avg_loss = _wilder_smooth(losses, window).iloc[-1]
    if pd.isna(avg_gain) or pd.isna(avg_loss):
        return None
    if avg_loss == 0:
        # No average downside over the smoothed history: RSI is 100 by definition
        # (and 50 in the degenerate flat case where there is no movement at all).
        return 100.0 if avg_gain > 0 else 50.0
    if avg_gain == 0:
        return 0.0
    rs = float(avg_gain) / float(avg_loss)
    return float(100.0 - 100.0 / (1.0 + rs))


def _true_range(df: pd.DataFrame) -> np.ndarray[Any, np.dtype[np.float64]]:
    """Per-bar true range, excluding the first bar (no previous close).

    ``TR = max(high - low, |high - prev_close|, |low - prev_close|)``. Shared by
    :func:`_atr` and :func:`_adx` so the two indicators agree on the same
    definition of a bar's range rather than each computing it independently.
    """
    high = df["high"].to_numpy(dtype="float64")
    low = df["low"].to_numpy(dtype="float64")
    close = df["close"].to_numpy(dtype="float64")
    prev_close = close[:-1]
    result: np.ndarray[Any, np.dtype[np.float64]] = np.maximum(
        high[1:] - low[1:],
        np.maximum(np.abs(high[1:] - prev_close), np.abs(low[1:] - prev_close)),
    )
    return result


def _atr(df: pd.DataFrame, window: int = 14) -> float | None:
    """Wilder's Average True Range over ``window`` periods.

    Smoothed with Wilder's method (:func:`_wilder_smooth`). The first bar has no
    previous close so its true range is undefined and is excluded rather than
    approximated by ``high - low`` — that approximation biases the seed on the very
    window it seeds. Covered by hand-computed golden tests in
    ``tests/unit/test_indicator_formulas.py``.
    """
    if len(df) < window + 1:
        return None
    tr = _true_range(df)
    val = _wilder_smooth(pd.Series(tr), window).iloc[-1]
    return float(val) if not pd.isna(val) else None


def _adx(df: pd.DataFrame, window: int = 14) -> tuple[float | None, float | None, float | None]:
    """Wilder's ADX(14) with +DI/-DI, per Wilder's original published method.

    For each bar (excluding the first, which has no previous bar to diff against):
      up_move = high_t - high_{t-1}; down_move = low_{t-1} - low_t
      +DM = up_move   if up_move > down_move and up_move > 0   else 0
      -DM = down_move if down_move > up_move and down_move > 0 else 0
    +DM, -DM, and TR (:func:`_true_range`) are each Wilder-smoothed over ``window``.
      +DI = 100 * smoothed(+DM) / smoothed(TR)
      -DI = 100 * smoothed(-DM) / smoothed(TR)
      DX  = 100 * |+DI - -DI| / (+DI + -DI)
    ADX is DX itself Wilder-smoothed over ``window`` -- a second smoothing pass, so
    ADX needs roughly ``2 * window`` bars of true range (``2*window + 1`` bars of
    price) before it stabilizes; fewer than that returns ``None`` for ADX while
    +DI/-DI (needing only one smoothing pass) may already be defined.

    Returns:
        ``(adx, plus_di, minus_di)``, each ``None`` if there isn't enough history.
    """
    if len(df) < window + 1:
        return None, None, None

    high = df["high"].to_numpy(dtype="float64")
    low = df["low"].to_numpy(dtype="float64")
    up_move = high[1:] - high[:-1]
    down_move = low[:-1] - low[1:]

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr = _true_range(df)

    smoothed_plus_dm = _wilder_smooth(pd.Series(plus_dm), window)
    smoothed_minus_dm = _wilder_smooth(pd.Series(minus_dm), window)
    smoothed_tr = _wilder_smooth(pd.Series(tr), window)

    with np.errstate(invalid="ignore", divide="ignore"):
        plus_di = 100.0 * smoothed_plus_dm / smoothed_tr
        minus_di = 100.0 * smoothed_minus_dm / smoothed_tr
        di_sum = plus_di + minus_di
        dx = 100.0 * (plus_di - minus_di).abs() / di_sum
    dx = dx.where(di_sum != 0, 0.0)

    # dx inherits (window - 1) leading NaNs from the first smoothing pass
    # (smoothed_plus_dm/smoothed_tr are undefined until the DM/TR seed).
    # _wilder_smooth's own seeding rule -- "average the first `window`
    # entries" -- must be applied to `window` *real* DX values, the way
    # Wilder's published ADX seeds itself (a simple average of the first
    # `window` DX readings). Passing the NaN-prefixed series straight through
    # would instead seed on a single real value (whatever lands at position
    # `window - 1`, which is NaN here), silently discarding almost the entire
    # seed window. Dropping the leading NaNs first re-aligns "the first
    # `window` entries" with "the first `window` real DX values".
    dx_valid = dx.dropna().reset_index(drop=True)
    adx_val = (
        _wilder_smooth(dx_valid, window).iloc[-1] if len(dx_valid) >= window else float("nan")
    )

    plus_di_val = plus_di.iloc[-1]
    minus_di_val = minus_di.iloc[-1]

    return (
        float(adx_val) if not pd.isna(adx_val) else None,
        float(plus_di_val) if not pd.isna(plus_di_val) else None,
        float(minus_di_val) if not pd.isna(minus_di_val) else None,
    )


def _macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[float | None, float | None, float | None]:
    """MACD(12,26,9): fast/slow EMA crossover with a signal-line EMA of the MACD line.

      macd_line = EMA(fast) - EMA(slow)
      signal_line = EMA(signal) of macd_line
      histogram = macd_line - signal_line

    Uses the same :func:`_ema` (pandas ``ewm(span=...)``) as the existing
    ema10/ema21 fields, so all EMA-based indicators in this pipeline share one
    definition. Requires ``slow + signal`` bars for the signal line to have fully
    absorbed its own seed transient.

    Returns:
        ``(macd_line, signal_line, histogram)``, each ``None`` if insufficient history.
    """
    if len(close) < slow + signal:
        return None, None, None
    macd_line_series = _ema(close, fast) - _ema(close, slow)
    signal_series = _ema(macd_line_series, signal)
    histogram_series = macd_line_series - signal_series

    macd_val = macd_line_series.iloc[-1]
    signal_val = signal_series.iloc[-1]
    hist_val = histogram_series.iloc[-1]
    if pd.isna(macd_val) or pd.isna(signal_val) or pd.isna(hist_val):
        return None, None, None
    return float(macd_val), float(signal_val), float(hist_val)


def _swing_levels(
    df: pd.DataFrame, left: int = 5, right: int = 5
) -> tuple[float | None, float | None]:
    """Nearest confirmed N-bar fractal swing resistance/support above/below the latest close.

    A bar at index ``i`` is a swing high if its high exceeds the high of every bar
    in ``[i-left, i+right]`` around it (swing low: symmetric on lows). A pivot needs
    ``right`` bars *after* it to be confirmed, so the most recent ``right`` bars can
    never themselves be pivots -- this is a real constraint of the method, not a
    data gap: a fractal swing high is only knowable in hindsight.

    Unlike the fixed 20-day high/low window used internally by the breakout engine,
    this returns the nearest actual swing point to the current price on each side,
    which is what a stop-loss/target needs (Phase 3) rather than an arbitrary
    calendar window.

    Returns:
        ``(nearest_resistance, nearest_support)`` -- the confirmed swing high
        closest above the latest close, and the confirmed swing low closest below
        it. Either may be ``None`` if no such confirmed pivot exists in history.
    """
    n = len(df)
    min_bars = left + right + 1
    if n < min_bars:
        return None, None

    high = df["high"].to_numpy(dtype="float64")
    low = df["low"].to_numpy(dtype="float64")
    latest_close = float(df["close"].to_numpy(dtype="float64")[-1])

    swing_highs: list[float] = []
    swing_lows: list[float] = []
    # Only pivots with `right` bars after them are confirmed -- i.e. up to
    # index n - 1 - right.
    for i in range(left, n - right):
        window_high = high[i - left : i + right + 1]
        if high[i] == window_high.max() and (window_high == high[i]).sum() == 1:
            swing_highs.append(high[i])
        window_low = low[i - left : i + right + 1]
        if low[i] == window_low.min() and (window_low == low[i]).sum() == 1:
            swing_lows.append(low[i])

    resistances_above = [h for h in swing_highs if h > latest_close]
    supports_below = [s for s in swing_lows if s < latest_close]

    nearest_resistance = float(min(resistances_above)) if resistances_above else None
    nearest_support = float(max(supports_below)) if supports_below else None
    return nearest_resistance, nearest_support


def _adr_pct(df: pd.DataFrame, window: int = 20) -> float | None:
    """Average Daily Range % over ``window`` periods.

    ADR% = mean(high / low - 1) over last ``window`` * 100.
    """
    if len(df) < window:
        return None
    recent = df.iloc[-window:]
    ratios = recent["high"].values / recent["low"].values - 1.0
    return float(np.mean(ratios) * 100.0)


def _stochastic(
    df: pd.DataFrame, window: int = 14, smooth: int = 3
) -> tuple[float | None, float | None]:
    """Fast Stochastic %K(``window``) and %D = SMA(``smooth``) of %K.

      %K_t = 100 * (close_t - min(low, window)) / (max(high, window) - min(low, window))
      %D_t = SMA(smooth) of %K

    A flat range (max high == min low) leaves %K undefined -- there is no
    position within a zero-width range -- and returns ``None`` rather than a
    substituted 50 or 0.

    %K and %D are resolved independently: %K needs ``window`` bars, %D needs
    ``window + smooth - 1``, so a series can legitimately have one and not the
    other.
    """
    if len(df) < window:
        return None, None
    high_max = df["high"].rolling(window=window).max()
    low_min = df["low"].rolling(window=window).min()
    span = high_max - low_min
    percent_k = 100.0 * (df["close"] - low_min) / span.where(span != 0)
    percent_d = percent_k.rolling(window=smooth).mean()
    k_val, d_val = percent_k.iloc[-1], percent_d.iloc[-1]
    return (
        float(k_val) if not pd.isna(k_val) else None,
        float(d_val) if not pd.isna(d_val) else None,
    )


def _williams_r(df: pd.DataFrame, window: int = 14) -> float | None:
    """Williams %R over ``window``: ``-100 * (max_high - close) / (max_high - min_low)``.

    Range ``[-100, 0]``. Algebraically ``%K - 100`` for the same window; both are
    reported because both are conventional displays and readers expect the scale
    they know, not a derivation they have to perform.
    """
    if len(df) < window:
        return None
    high_max = float(df["high"].iloc[-window:].max())
    low_min = float(df["low"].iloc[-window:].min())
    if high_max == low_min:
        return None
    return -100.0 * (high_max - float(df["close"].iloc[-1])) / (high_max - low_min)


def _cci(df: pd.DataFrame, window: int = 20) -> float | None:
    """Commodity Channel Index over ``window``.

      TP = (high + low + close) / 3
      CCI = (TP - SMA(TP, window)) / (0.015 * mean_absolute_deviation(TP, window))

    The 0.015 constant is Lambert's original scaling. Note the denominator is the
    *mean absolute deviation*, not the standard deviation -- substituting the
    latter (a common error) shifts every reading and breaks the conventional
    ±100 reference points. Zero deviation (a perfectly flat window) is undefined
    and returns ``None``.
    """
    if len(df) < window:
        return None
    tp = (df["high"] + df["low"] + df["close"]) / 3.0
    recent = tp.iloc[-window:]
    mean_tp = float(recent.mean())
    mad = float((recent - mean_tp).abs().mean())
    if mad == 0:
        return None
    return (float(tp.iloc[-1]) - mean_tp) / (0.015 * mad)


def _roc(close: pd.Series, window: int = 12) -> float | None:
    """Rate of Change: percent change of close over ``window`` sessions."""
    if len(close) < window + 1:
        return None
    prior = float(close.iloc[-(window + 1)])
    if prior == 0:
        return None
    return (float(close.iloc[-1]) / prior - 1.0) * 100.0


def _pct_from(close: float, ma: float | None) -> float | None:
    """Signed percentage distance of ``close`` from a moving average."""
    if ma is None or ma == 0:
        return None
    return (close / ma - 1.0) * 100.0


def _sma_slope(close: pd.Series, sma_window: int, slope_window: int) -> float | None:
    """Return the SMA percentage change over ``slope_window`` trading days.

    slope = (SMA_current / SMA_prior) - 1 expressed as percentage.
    """
    if len(close) < sma_window + slope_window:
        return None
    sma = close.rolling(window=sma_window).mean()
    current = sma.iloc[-1]
    prior = sma.iloc[-(slope_window + 1)]
    if pd.isna(current) or pd.isna(prior) or prior == 0:
        return None
    return float(((current / prior) - 1.0) * 100)


class IndicatorPipelineImpl:
    """Computes technical indicators deterministically using vectorized pandas.

    Queries enough trading days of history to cover the strategy's configured
    windows (``indicators.sma_windows``, ``high_low_window``, etc. -- see
    ``strategy.config.indicators``, ADR-005) relative to ``reference_date``,
    then computes all indicators using verified formulas. Returns None fields
    when there is insufficient history for the configured windows.
    """

    # The daily-bar source table. Overridable so a subclass can point the exact
    # same indicator logic at an alternate bar source (e.g. the legacy archive)
    # without duplicating any formula (ADR-005/ADR-009: one code path, one result).
    _model: Any =OHLCVDailyModel

    def __init__(self, session: AsyncSession) -> None:
        """Bind to an async DB session for historical bar retrieval."""
        self._session = session

    async def compute(
        self, symbol: str, reference_date: date, config: dict[str, Any]
    ) -> IndicatorSet:
        """Return the :class:`IndicatorSet` for *symbol* as of *reference_date*.

        Args:
            symbol: Ticker symbol (e.g., ``"RELIANCE"``).
            reference_date: The date for which indicators are computed.
            config: Pipeline configuration (indicator windows, etc.).

        Returns:
            A fully populated :class:`IndicatorSet`, or one with ``None`` indicators
            if there is insufficient history.
        """
        sma_windows = self._sma_windows(config)
        slope_window = int(config.get("sma200_slope_window", _DEFAULT_SLOPE_WINDOW))
        high_low_window = int(config.get("high_low_window", _DEFAULT_HIGH_LOW_WINDOW))
        avg_volume_window = int(config.get("avg_volume_window", _DEFAULT_AVG_VOLUME_WINDOW))
        min_bars = (
            max(sma_windows[-1] + slope_window, high_low_window, avg_volume_window)
            + _MIN_BARS_BUFFER
        )

        bars = await self._fetch_bars(symbol, reference_date, min_bars)
        if bars is None or len(bars) < min_bars:
            _logger.warning(
                "insufficient_history",
                symbol=symbol,
                date=reference_date.isoformat(),
                bars=len(bars) if bars is not None else 0,
                required=min_bars,
            )
            return IndicatorSet(as_of=reference_date)

        df = self._to_dataframe(bars)
        close_series = df["close"]

        latest_close = float(close_series.iloc[-1])

        # ── SMAs (short/mid/long per the strategy's configured windows) ────
        sma50 = _sma(close_series, sma_windows[0])
        sma150 = _sma(close_series, sma_windows[1])
        sma200 = _sma(close_series, sma_windows[2])

        # ── EMAs ────────────────────────────────────────────────────────
        ema10_raw = _ema(close_series, 10).iloc[-1] if len(close_series) >= 10 else None
        ema10 = float(ema10_raw) if ema10_raw is not None and not pd.isna(ema10_raw) else None
        ema21_raw = _ema(close_series, 21).iloc[-1] if len(close_series) >= 21 else None
        ema21 = float(ema21_raw) if ema21_raw is not None and not pd.isna(ema21_raw) else None

        # ── RSI ─────────────────────────────────────────────────────────
        rsi14 = _rsi(close_series, 14)

        # ── ATR ─────────────────────────────────────────────────────────
        atr14 = _atr(df, 14)

        # ── ADR% ────────────────────────────────────────────────────────
        adr_pct_value = _adr_pct(df, 20)

        # ── 52-week (or configured lookback) extremes ───────────────────
        high_52w, low_52w = self._extremes(df, high_low_window)
        pct_above_low_52w = (
            ((latest_close - low_52w) / low_52w * 100) if low_52w and low_52w > 0 else None
        )
        pct_below_high_52w = (
            ((high_52w - latest_close) / high_52w * 100) if high_52w and high_52w > 0 else None
        )

        # ── Long-SMA slope ──────────────────────────────────────────────
        sma200_slope_pct = _sma_slope(close_series, sma_windows[2], slope_window)

        # ── RS rating (stub — real RS computed by RelativeStrengthPipeline) ─
        rs_rating = None  # Will be populated by the orchestrator
        rs_line_slope = None

        # ── Volume indicators ───────────────────────────────────────────
        avg_volume50 = self._avg_volume(df, avg_volume_window)
        rel_volume = self._rel_volume(df, avg_volume_window)

        # ── ADX(14) + DI+/DI- (Phase 2.1) ────────────────────────────────
        adx14, plus_di14, minus_di14 = _adx(df, 14)

        # ── MACD(12,26,9) (Phase 2.2) ────────────────────────────────────
        macd_line, macd_signal, macd_histogram = _macd(close_series)

        # ── Swing pivot support/resistance (Phase 2.3) ───────────────────
        swing_resistance, swing_support = _swing_levels(df)

        # ── Distance from key moving averages (Phase 6.3) ────────────────
        pct_from_sma50 = _pct_from(latest_close, sma50)
        pct_from_sma200 = _pct_from(latest_close, sma200)

        # ── Additional raw oscillators (Phase 6.4) ───────────────────────
        stoch_k14, stoch_d14 = _stochastic(df, 14, 3)
        williams_r14 = _williams_r(df, 14)
        cci20 = _cci(df, 20)
        roc12 = _roc(close_series, 12)

        # Egress boundary: quantize every float metric to a fixed-precision Decimal
        return IndicatorSet(
            as_of=reference_date,
            sma50=_quantize(sma50),
            sma150=_quantize(sma150),
            sma200=_quantize(sma200),
            ema10=_quantize(ema10),
            ema21=_quantize(ema21),
            rsi14=_quantize(rsi14),
            atr14=_quantize(atr14),
            adr_pct=_quantize(adr_pct_value),
            high_52w=_quantize(high_52w),
            low_52w=_quantize(low_52w),
            pct_above_low_52w=_quantize(pct_above_low_52w),
            pct_below_high_52w=_quantize(pct_below_high_52w),
            sma200_slope_pct=_quantize(sma200_slope_pct),
            rs_rating=rs_rating,
            rs_line_slope=_quantize(rs_line_slope),
            avg_volume50=_quantize(avg_volume50),
            rel_volume=_quantize(rel_volume),
            adx14=_quantize(adx14),
            plus_di14=_quantize(plus_di14),
            minus_di14=_quantize(minus_di14),
            macd_line=_quantize(macd_line),
            macd_signal=_quantize(macd_signal),
            macd_histogram=_quantize(macd_histogram),
            swing_resistance=_quantize(swing_resistance),
            swing_support=_quantize(swing_support),
            pct_from_sma50=_quantize(pct_from_sma50),
            pct_from_sma200=_quantize(pct_from_sma200),
            stoch_k14=_quantize(stoch_k14),
            stoch_d14=_quantize(stoch_d14),
            williams_r14=_quantize(williams_r14),
            cci20=_quantize(cci20),
            roc12=_quantize(roc12),
        )

    @staticmethod
    def _sma_windows(config: dict[str, Any]) -> tuple[int, int, int]:
        """Return the (short, mid, long) SMA windows from config, or the 1-Year defaults."""
        windows = config.get("sma_windows")
        if not windows or len(windows) != 3:
            return _DEFAULT_SMA_WINDOWS
        return int(windows[0]), int(windows[1]), int(windows[2])

    async def _fetch_bars(
        self, symbol: str, reference_date: date, min_bars: int
    ) -> list[Any] | None:
        """Retrieve historical bars for *symbol* up to *reference_date*."""
        from momentum25.infrastructure.persistence.models import SecurityModel

        model = self._model
        sec_subq = (
            select(SecurityModel.id)
            .where(SecurityModel.symbol == symbol, SecurityModel.is_active.is_(True))
            .limit(1)
            .scalar_subquery()
        )
        stmt = (
            select(model)
            .where(
                model.security_id == sec_subq,
                model.date <= reference_date,
            )
            .order_by(model.date.desc())
            .limit(min_bars)
        )
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        if not rows:
            return None
        return list(reversed(rows))

    @staticmethod
    def _to_dataframe(bars: list[Any]) -> pd.DataFrame:
        """Convert ORM bar rows to a pandas DataFrame indexed by date.

        Applies each bar's corporate-action ``adj_factor`` (default 1, i.e. a
        no-op until Phase 1's adjustment engine populates it): OHLC is
        multiplied and volume divided, matching
        ``domain.entities.market_data.compute_adjustment_factors``'s contract.
        """
        # The legacy archive carries raw prints only (no adjustment columns);
        # a missing ``adj_factor`` is treated as 1.0 (no-op). This is exactly
        # behaviour-preserving for the live table, where ``adj_factor`` is 1 for
        # every row until the Phase 1 adjustment engine populates it.
        factors = [float(getattr(b, "adj_factor", None) or 1) for b in bars]
        data = {
            "date": [b.date for b in bars],
            "open": [float(b.open) * f for b, f in zip(bars, factors, strict=True)],
            "high": [float(b.high) * f for b, f in zip(bars, factors, strict=True)],
            "low": [float(b.low) * f for b, f in zip(bars, factors, strict=True)],
            "close": [float(b.close) * f for b, f in zip(bars, factors, strict=True)],
            "volume": [b.volume / f for b, f in zip(bars, factors, strict=True)],
        }
        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["date"])
        return df

    @staticmethod
    def _extremes(df: pd.DataFrame, window_size: int) -> tuple[float | None, float | None]:
        """Return (high, low) over the trailing ``window_size`` trading days."""
        if len(df) < window_size:
            return None, None
        window = df.iloc[-window_size:]
        return float(window["high"].max()), float(window["low"].min())

    @staticmethod
    def _avg_volume(df: pd.DataFrame, window: int = 50) -> float | None:
        """Average volume over the trailing ``window`` days."""
        if len(df) < window:
            return None
        return float(df["volume"].iloc[-window:].mean())

    @staticmethod
    def _rel_volume(df: pd.DataFrame, window: int = 50) -> float | None:
        """Relative volume: latest volume / average volume over ``window`` (excluding latest)."""
        if len(df) < window + 1:
            return None
        avg_vol = float(df["volume"].iloc[-window:-1].mean())
        if avg_vol == 0:
            return None
        latest_vol = float(df["volume"].iloc[-1])
        return latest_vol / avg_vol


class LegacyIndicatorPipelineImpl(IndicatorPipelineImpl):
    """Indicator pipeline pointed at the legacy archive (``legacy_ohlcv_daily``).

    Identical formulas and code path as :class:`IndicatorPipelineImpl` — only the
    daily-bar source table differs. Used by the pre-2019 historical-screening
    backfill so that scores computed against the legacy archive are byte-for-byte
    comparable to live production scores (same engine, same rules, same weights).
    """

    _model: Any =LegacyOHLCVDailyModel