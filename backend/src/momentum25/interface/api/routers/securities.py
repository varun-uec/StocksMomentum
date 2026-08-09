"""Security price-series endpoints (for charts)."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from momentum25.application.dto.market_data import SecurityOHLCVDTO, SecuritySearchResultDTO
from momentum25.application.use_cases.securities import GetSecurityOHLCV, SearchSecurities
from momentum25.interface.api.dependencies import (
    get_get_security_ohlcv,
    get_search_securities,
)

router = APIRouter(prefix="/securities", tags=["securities"])


@router.get("", response_model=list[SecuritySearchResultDTO])
async def search_securities(
    use_case: Annotated[SearchSecurities, Depends(get_search_securities)],
    q: Annotated[str, Query(min_length=1, max_length=64)],
    limit: Annotated[int, Query(ge=1, le=25)] = 10,
) -> list[SecuritySearchResultDTO]:
    """Return symbol suggestions matching *q* on symbol or company name."""
    return await use_case.execute(q, limit)


@router.get("/{symbol}/ohlcv", response_model=SecurityOHLCVDTO)
async def get_ohlcv(
    symbol: str,
    use_case: Annotated[GetSecurityOHLCV, Depends(get_get_security_ohlcv)],
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: Annotated[date | None, Query()] = None,
) -> SecurityOHLCVDTO:
    """Return a symbol's OHLCV series for charting."""
    return await use_case.execute(symbol, from_, to)
