"""Chart-pattern detection endpoint (Phase 8) — chart annotation, no verdict.

``POST`` rather than ``GET``: detection is an explicitly user-triggered action,
never something a page load performs for every visitor. The verb keeps that
contract visible in the API itself and keeps the result out of shared caches.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from momentum25.application.use_cases.chart_patterns import DetectChartPatterns
from momentum25.domain.analytics.chart_patterns import ChartPatternAnalysis
from momentum25.interface.api.dependencies import get_detect_chart_patterns

router = APIRouter(prefix="/stocks", tags=["chart-patterns"])


@router.post("/{symbol}/chart-patterns", response_model=ChartPatternAnalysis)
async def detect_chart_patterns_endpoint(
    symbol: str,
    use_case: Annotated[DetectChartPatterns, Depends(get_detect_chart_patterns)],
    lookback_days: Annotated[int, Query(ge=60, le=2000)] = 500,
    threshold_pct: Annotated[Decimal, Query(gt=0, le=50)] = Decimal("5"),
) -> ChartPatternAnalysis:
    """Return the classical chart patterns the stored price history supports.

    ``threshold_pct`` is the zigzag reversal size that confirms a pivot, so a
    larger threshold recognises larger formations. Every candidate that meets
    its structural criteria is returned; an empty list means nothing qualified,
    which is the honest answer rather than an error. No target price and no
    directional call is derived from any pattern.
    """
    return await use_case.execute(symbol, lookback_days, threshold_pct)
