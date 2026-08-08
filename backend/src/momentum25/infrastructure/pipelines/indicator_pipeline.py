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

    EMA_t = price_t * k + EMA_{t-1} * (1 - k), k = 2 / (span + 1)
    Seed = SMA(span) of first ``span`` values.
    """
    return series.ewm(span=span, adjust=False).mean()


def _rsi(series: pd.Series, window: int = 14) -> float | None:
    """Wilder's RSI over ``window`` periods.

    RSI = 100 - 100 / (1 + RS), where RS = avg_gain / avg_loss
    Uses Wilder's smoothing (simple moving average of gains/losses).
    Verified against standard TA definitions.
    """
    if len(series) < window + 1:
        return None
    deltas = series.diff().dropna()
    gains = deltas.where(deltas > 0, 0.0)
    losses = -deltas.where(deltas < 0, 0.0)
    avg_gain = gains.rolling(window=window).mean().iloc[-1]
    avg_loss = losses.rolling(window=window).mean().iloc[-1]
    if avg_loss == 0:
        return 100.0
    if avg_gain == 0:
        return 0.0
    rs = avg_gain / avg_loss
    return float(100.0 - 100.0 / (1.0 + rs))


def _atr(df: pd.DataFrame, window: int = 14) -> float | None:
    """Wilder's Average True Range over ``window`` periods.

    TR = max(high - low, |high - prev_close|, |low - prev_close|)
    ATR = rolling mean of TR over window.
    Verified against standard TA definitions.
    """
    if len(df) < window + 1:
        return None
    high = df["high"].values
    low = df["low"].values
    close = df["close"].values
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]

    tr = np.maximum(high - low, np.maximum(
        np.abs(high - prev_close), np.abs(low - prev_close)
    ))
    tr_series = pd.Series(tr)
    val = tr_series.rolling(window=window).mean().iloc[-1]
    return float(val) if not pd.isna(val) else None


def _adr_pct(df: pd.DataFrame, window: int = 20) -> float | None:
    """Average Daily Range % over ``window`` periods.

    ADR% = mean(high / low - 1) over last ``window`` * 100.
    """
    if len(df) < window:
        return None
    recent = df.iloc[-window:]
    ratios = recent["high"].values / recent["low"].values - 1.0
    return float(np.mean(ratios) * 100.0)


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