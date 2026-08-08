"""Security price-series endpoints (for charts)."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from momentum25.application.dto.market_data import OHLCVBarDTO, SecurityOHLCVDTO
from momentum25.domain.errors import NotFoundError
from momentum25.infrastructure.persistence.repositories import (
    SqlOHLCVRepository,
    SqlSecurityRepository,
)
from momentum25.interface.api.dependencies import get_ohlcv_repo, get_security_repo

router = APIRouter(prefix="/securities", tags=["securities"])


@router.get("/{symbol}/ohlcv", response_model=SecurityOHLCVDTO)
async def get_ohlcv(
    symbol: str,
    securities: Annotated[SqlSecurityRepository, Depends(get_security_repo)],
    ohlcv: Annotated[SqlOHLCVRepository, Depends(get_ohlcv_repo)],
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: Annotated[date | None, Query()] = None,
) -> SecurityOHLCVDTO:
    """Return a symbol's OHLCV series for charting."""
    security = await securities.get_by_symbol(symbol)
    if security is None or security.id is None:
        raise NotFoundError(f"Security not found: {symbol}")
    as_of = to or date.today()
    series = await ohlcv.get_series(security.id, lookback_days=500, as_of=as_of)
    bars = [
        OHLCVBarDTO(
            date=b.date, open=b.open, high=b.high, low=b.low, close=b.close, volume=b.volume
        )
        for b in series.bars
        if from_ is None or b.date >= from_
    ]
    return SecurityOHLCVDTO(symbol=str(security.symbol), bars=bars)
