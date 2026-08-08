"""Universe-level market-context endpoints (Phase 6.6/6.7)."""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from momentum25.application.use_cases.market_context import GetMarketContext, MarketContext
from momentum25.interface.api.dependencies import get_market_context

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/context", response_model=MarketContext)
async def read_market_context(
    use_case: Annotated[GetMarketContext, Depends(get_market_context)],
    as_of: Annotated[date | None, Query()] = None,
) -> MarketContext:
    """Return universe breadth and the sector relative-strength ranking.

    Descriptive figures only: counts, percentages and excess returns for the
    tracked universe as a whole. Nothing here is a per-stock signal, and none of
    it feeds the composite score or the ranking.

    Defaults to the latest stored bar date rather than today, so the panel
    reports the last session actually measured.
    """
    return await use_case.execute(as_of)
