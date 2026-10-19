"""Strategy Studio endpoints (FR-25, ADR-014): the rule registry, families, user strategies."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from momentum25.application.dto.studio import (
    CreateFamilyRequest,
    FamilyDTO,
    RuleRegistryDTO,
    SaveStrategyRequest,
    StudioStrategyDTO,
)
from momentum25.application.use_cases.studio import (
    CreateFamily,
    GetRuleRegistry,
    ListFamilies,
    SaveStrategy,
)
from momentum25.interface.api.dependencies import (
    get_create_family,
    get_list_families,
    get_save_strategy,
)

router = APIRouter(prefix="/studio", tags=["studio"])


@router.get("/rules", response_model=RuleRegistryDTO)
async def rule_registry() -> RuleRegistryDTO:
    """Every engine, rule and parameter a user strategy may set, with bounds."""
    return GetRuleRegistry().execute()


@router.get("/families", response_model=list[FamilyDTO])
async def list_families(
    use_case: Annotated[ListFamilies, Depends(get_list_families)],
) -> list[FamilyDTO]:
    """Every family with its hypothesis, root and members."""
    return await use_case.execute()


@router.post("/families", response_model=FamilyDTO, status_code=201)
async def create_family(
    request: CreateFamilyRequest,
    use_case: Annotated[CreateFamily, Depends(get_create_family)],
) -> FamilyDTO:
    """State a hypothesis and save its first config, from a strategy file or from scratch."""
    return await use_case.execute(request)


@router.post("/families/{family_id}/strategies", response_model=StudioStrategyDTO, status_code=201)
async def save_strategy(
    family_id: int,
    request: SaveStrategyRequest,
    use_case: Annotated[SaveStrategy, Depends(get_save_strategy)],
) -> StudioStrategyDTO:
    """Save a new config derived from the family's root or one of its members."""
    return await use_case.execute(family_id, request)
