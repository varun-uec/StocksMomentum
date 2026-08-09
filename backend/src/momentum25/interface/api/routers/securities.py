"""Security price-series endpoints (for charts)."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from momentum25.application.dto.market_data import SecurityOHLCVDTO
from momentum25.application.use_cases.securities import GetSecurityOHLCV
from momentum25.interface.api.dependencies import get_get_security_ohlcv

router = APIRouter(prefix="/securities", tags=["securities"])


@router.get("/{symbol}/ohlcv", response_model=SecurityOHLCVDTO)
async def get_ohlcv(
    symbol: str,
    use_case: Annotated[GetSecurityOHLCV, Depends(get_get_security_ohlcv)],
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: Annotated[date | None, Query()] = None,
) -> SecurityOHLCVDTO:
    """Return a symbol's OHLCV series for charting."""
    return await use_case.execute(symbol, from_, to)
