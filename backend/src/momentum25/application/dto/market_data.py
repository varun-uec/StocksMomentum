"""Market-data DTOs (price series for charts)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class OHLCVBarDTO(BaseModel):
    """A single OHLCV bar for chart rendering."""

    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


class SecurityOHLCVDTO(BaseModel):
    """A symbol's price series."""

    symbol: str
    bars: list[OHLCVBarDTO]


class IndicatorBarDTO(BaseModel):
    """One day's indicator values for the chart sub-panes (Phase 9).

    ``None`` fields mean the indicator was undefined that bar (warm-up or
    insufficient history). Every value is the same quantized series the
    snapshot endpoint reports as its latest value.
    """

    date: date
    rsi14: Decimal | None = None
    atr14: Decimal | None = None
    adx14: Decimal | None = None
    macd_line: Decimal | None = None
    macd_signal: Decimal | None = None
    macd_histogram: Decimal | None = None


class SecurityIndicatorSeriesDTO(BaseModel):
    """A symbol's per-bar indicator series."""

    symbol: str
    bars: list[IndicatorBarDTO]
