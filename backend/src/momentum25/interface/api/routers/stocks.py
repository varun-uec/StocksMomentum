"""Stock detail, explainability, and history endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from momentum25.application.use_cases.stocks import GetStockExplanation, GetStockHistory
from momentum25.domain.scoring.explainability import StockExplanation
from momentum25.interface.api.dependencies import get_stock_explanation, get_stock_history

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("/{symbol}", response_model=StockExplanation)
async def read_stock(
    symbol: str,
    use_case: Annotated[GetStockExplanation, Depends(get_stock_explanation)],
    run_id: Annotated[int | None, Query()] = None,
    strategy: Annotated[str, Query()] = "minervini_trend_template",
) -> StockExplanation:
    """Return a stock's full score breakdown and explanation for a run.

    If ``run_id`` is omitted, resolves to the latest completed run for
    ``strategy`` (e.g. a Momentum Horizon) rather than the latest run
    across every strategy.
    """
    return await use_case.execute(symbol, run_id, strategy)


@router.get("/{symbol}/history")
async def read_stock_history(
    symbol: str,
    use_case: Annotated[GetStockHistory, Depends(get_stock_history)],
    strategy: Annotated[str, Query()] = "minervini_trend_template",
    limit: Annotated[int, Query(ge=1, le=500)] = 90,
) -> Any:
    """Return a stock's score/rank history across runs."""
    return await use_case.execute(symbol, strategy, limit)
