"""Ranking and explanation endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from momentum25.application.dto.rankings import RankingsResponseDTO
from momentum25.application.use_cases.rankings import GetRankings, GetStockExplanation
from momentum25.domain.scoring.explainability import StockExplanation
from momentum25.interface.api.dependencies import get_get_rankings, get_get_stock_explanation

router = APIRouter(prefix="/rankings", tags=["rankings"])


@router.get("/runs/{run_id}", response_model=RankingsResponseDTO)
async def get_rankings(
    run_id: int,
    use_case: Annotated[GetRankings, Depends(get_get_rankings)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> RankingsResponseDTO:
    """Return paginated rankings for a completed screening run."""
    return await use_case.execute(run_id, limit=limit, offset=offset)


@router.get(
    "/runs/{run_id}/stocks/{security_id}/explanation",
    response_model=StockExplanation,
)
async def get_stock_explanation(
    run_id: int,
    security_id: int,
    use_case: Annotated[GetStockExplanation, Depends(get_get_stock_explanation)],
) -> StockExplanation:
    """Return full explainability for a single stock in a run."""
    return await use_case.execute(run_id, security_id)