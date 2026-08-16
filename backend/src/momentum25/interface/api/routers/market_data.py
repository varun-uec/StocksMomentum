"""Market-data ingestion endpoints (manual latest-session refresh)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from momentum25.application.dto.market_data import (
    RefreshMarketDataRequest,
    RefreshMarketDataResponse,
)
from momentum25.application.use_cases.market_data import RefreshLatestMarketData
from momentum25.interface.api.dependencies import get_refresh_latest_market_data

router = APIRouter(prefix="/market-data", tags=["market-data"])


@router.post("/refresh", response_model=RefreshMarketDataResponse)
async def refresh_latest_market_data(
    body: RefreshMarketDataRequest,
    use_case: Annotated[RefreshLatestMarketData, Depends(get_refresh_latest_market_data)],
) -> RefreshMarketDataResponse:
    """Ingest the latest completed trading session for the requested exchanges.

    Synchronous: one bhavcopy fetch and one bulk upsert per exchange. Repeat
    calls for the same session are idempotent (``ON CONFLICT DO UPDATE``).
    This does not start a screening run.
    """
    summary = await use_case.execute(list(body.exchanges))
    return RefreshMarketDataResponse.from_summary(summary)
