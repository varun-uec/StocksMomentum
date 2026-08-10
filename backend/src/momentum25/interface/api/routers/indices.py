"""Benchmark-index price-series endpoints (for chart overlays)."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from momentum25.application.dto.market_data import IndexOHLCVDTO
from momentum25.application.use_cases.securities import GetIndexCloseSeries
from momentum25.interface.api.dependencies import get_get_index_close_series

router = APIRouter(prefix="/indices", tags=["indices"])


@router.get("/{index_code}/closes", response_model=IndexOHLCVDTO)
async def get_index_closes(
    index_code: str,
    use_case: Annotated[GetIndexCloseSeries, Depends(get_get_index_close_series)],
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: Annotated[date | None, Query()] = None,
) -> IndexOHLCVDTO:
    """Return a benchmark index's daily close series for charting."""
    return await use_case.execute(index_code, from_, to)
