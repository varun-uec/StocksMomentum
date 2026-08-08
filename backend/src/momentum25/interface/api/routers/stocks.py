"""Stock detail, explainability, and history endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from momentum25.application.use_cases.stocks import (
    GetLiveStockAnalysis,
    GetStockExplanation,
    GetStockHistory,
    LiveStockAnalysis,
)
from momentum25.domain.scoring.explainability import StockExplanation
from momentum25.interface.api.dependencies import (
    get_live_stock_analysis,
    get_stock_explanation,
    get_stock_history,
)

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


@router.get("/{symbol}/live", response_model=LiveStockAnalysis)
async def read_stock_live(
    symbol: str,
    use_case: Annotated[GetLiveStockAnalysis, Depends(get_live_stock_analysis)],
    refresh: Annotated[bool, Query()] = False,
    strategy: Annotated[str, Query()] = "minervini_trend_template",
) -> LiveStockAnalysis:
    """Evaluate a symbol on demand through the real strategy engine.

    With ``refresh=true``, fetches fresh bars from NSE first (subject to a
    per-symbol cooldown, Phase 1.3) rather than relying on the last batch
    screening run. Verdict is ``INDETERMINATE`` rather than ``FAILED`` when a
    rule (e.g. RS rating) could not be measured for a single symbol -- see
    ``GetLiveStockAnalysis`` for why.
    """
    return await use_case.execute(symbol, strategy, refresh)
