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
    workspace: Annotated[bool, Query()] = False,
) -> list[StrategySummaryDTO]:
    """List registered strategies.

    ``workspace=true`` includes every saved user version. ``with_runs=true``
    restricts either list to versions that have a completed live screening
    snapshot. The workstation uses the unfiltered list so selecting a version
    without a run can show an honest empty state.
    """
    return await use_case.execute(with_runs=with_runs, workspace=workspace)


@router.get("/{name}", response_model=StrategyDetailDTO)
async def get_strategy(
    name: str,
    use_case: Annotated[GetStrategy, Depends(get_get_strategy)],
) -> StrategyDetailDTO:
    """Return a single strategy and its configuration."""
    return await use_case.execute(name)
