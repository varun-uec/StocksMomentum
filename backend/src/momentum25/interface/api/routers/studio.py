"""Strategy Studio endpoints (FR-25, ADR-014): the rule registry, families, user strategies."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends

from momentum25.application.dto.studio import (
    CreateFamilyRequest,
    EvaluationDTO,
    FamilyDTO,
    RuleRegistryDTO,
    SaveStrategyRequest,
    StudioStrategyDTO,
    SubmitEvaluationRequest,
)
from momentum25.application.use_cases.strategy_evaluation import (
    GetEvaluation,
    ListEvaluations,
    RetryEvaluation,
    SubmitEvaluation,
)
from momentum25.application.use_cases.studio import (
    CreateFamily,
    GetRuleRegistry,
    ListFamilies,
    SaveStrategy,
)
from momentum25.interface.api.dependencies import (
    get_create_family,
    get_get_evaluation,
    get_list_evaluations,
    get_list_families,
    get_retry_evaluation,
    get_save_strategy,
    get_submit_evaluation,
    run_evaluation_job,
)
from momentum25.interface.api.params import EntityId

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
    family_id: EntityId,
    request: SaveStrategyRequest,
    use_case: Annotated[SaveStrategy, Depends(get_save_strategy)],
) -> StudioStrategyDTO:
    """Save a new config derived from the family's root or one of its members."""
    return await use_case.execute(family_id, request)


@router.post("/families/{family_id}/evaluations", response_model=EvaluationDTO, status_code=202)
async def submit_evaluation(
    family_id: EntityId,
    request: SubmitEvaluationRequest,
    background_tasks: BackgroundTasks,
    use_case: Annotated[SubmitEvaluation, Depends(get_submit_evaluation)],
) -> EvaluationDTO:
    """Queue an evaluation and run it after the response. Poll it for progress.

    An Out-of-Sample Evaluation spends the family's hold-out when it is queued.
    """
    evaluation = await use_case.execute(family_id, request)
    background_tasks.add_task(run_evaluation_job, evaluation.id)
    return evaluation


@router.get("/families/{family_id}/evaluations", response_model=list[EvaluationDTO])
async def list_evaluations(
    family_id: EntityId,
    use_case: Annotated[ListEvaluations, Depends(get_list_evaluations)],
) -> list[EvaluationDTO]:
    """A family's evaluations, newest first."""
    return await use_case.execute(family_id)


@router.get("/evaluations/{evaluation_id}", response_model=EvaluationDTO)
async def get_evaluation(
    evaluation_id: EntityId,
    use_case: Annotated[GetEvaluation, Depends(get_get_evaluation)],
) -> EvaluationDTO:
    """One evaluation with its progress and, once complete, its result."""
    return await use_case.execute(evaluation_id)


@router.post("/evaluations/{evaluation_id}/retry", response_model=EvaluationDTO, status_code=202)
async def retry_evaluation(
    evaluation_id: EntityId,
    background_tasks: BackgroundTasks,
    use_case: Annotated[RetryEvaluation, Depends(get_retry_evaluation)],
) -> EvaluationDTO:
    """Run a failed evaluation again, on the same window and data revision."""
    evaluation = await use_case.execute(evaluation_id)
    background_tasks.add_task(run_evaluation_job, evaluation.id)
    return evaluation
