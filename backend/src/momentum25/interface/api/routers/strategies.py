"""Strategy endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from momentum25.application.dto.strategies import StrategyDetailDTO, StrategySummaryDTO
from momentum25.application.use_cases.strategies import GetStrategy, ListStrategies
from momentum25.interface.api.dependencies import get_get_strategy, get_list_strategies

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("", response_model=list[StrategySummaryDTO])
async def list_strategies(
    use_case: Annotated[ListStrategies, Depends(get_list_strategies)],
    with_runs: Annotated[bool, Query()] = False,
) -> list[StrategySummaryDTO]:
    """List registered strategies.

    ``with_runs=true`` restricts the list to strategies with at least one
    completed live run, for building a strategy selector that can never
    present an option with nothing to show.
    """
    return await use_case.execute(with_runs=with_runs)


@router.get("/{name}", response_model=StrategyDetailDTO)
async def get_strategy(
    name: str,
    use_case: Annotated[GetStrategy, Depends(get_get_strategy)],
) -> StrategyDetailDTO:
    """Return a single strategy and its configuration."""
    return await use_case.execute(name)
