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
