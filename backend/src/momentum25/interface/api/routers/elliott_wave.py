"""Elliott Wave labelling endpoint (Phase 7) — chart annotation, no verdict."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from momentum25.application.use_cases.elliott_wave import GetElliottWaveAnalysis
from momentum25.domain.analytics.elliott_wave import ElliottWaveAnalysis
from momentum25.interface.api.dependencies import get_elliott_wave_analysis

router = APIRouter(prefix="/stocks", tags=["elliott-wave"])


@router.get("/{symbol}/elliott-wave", response_model=ElliottWaveAnalysis)
async def read_elliott_wave(
    symbol: str,
    use_case: Annotated[GetElliottWaveAnalysis, Depends(get_elliott_wave_analysis)],
    lookback_days: Annotated[int, Query(ge=60, le=2000)] = 500,
    threshold_pct: Annotated[Decimal, Query(gt=0, le=50)] = Decimal("5"),
) -> ElliottWaveAnalysis:
    """Return the wave count(s) the stored price history supports.

    ``threshold_pct`` is the zigzag reversal size that confirms a pivot: a larger
    threshold labels a larger degree. Returns pivots with no count when the
    history satisfies no valid structure -- that absence is the honest answer,
    not an error.
    """
    return await use_case.execute(symbol, lookback_days, threshold_pct)
