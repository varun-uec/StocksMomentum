"""Screening-run endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status

from momentum25.app.services.screening_job import run_screening_pipeline
from momentum25.application.dto.common import Page
from momentum25.application.dto.runs import RunDTO, TriggerRefreshRequest
from momentum25.application.use_cases.runs import (
    GetLatestRunForStrategy,
    GetRun,
    ListRuns,
    TriggerRefresh,
)
from momentum25.application.use_cases.screening import ExecuteScreening
from momentum25.infrastructure.config.settings import get_settings
from momentum25.interface.api.dependencies import (
    get_execute_screening,
    get_get_latest_run_for_strategy,
    get_get_run,
    get_list_runs,
    get_trigger_refresh,
)

router = APIRouter(prefix="/runs", tags=["runs"])


def _require_downloads_if_forced(force: bool) -> None:
    """Reject a requested full exchange refetch before creating a run row."""
    if force and not get_settings().direct_exchange_downloads_enabled:
        raise HTTPException(
            status_code=409,
            detail=(
                "Forced exchange downloads are disabled. "
                "Import authorized market data first or enable the adapter explicitly."
            ),
        )


@router.get("", response_model=Page[RunDTO])
async def list_runs(
    use_case: Annotated[ListRuns, Depends(get_list_runs)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[RunDTO]:
    """List screening runs (paginated, optionally filtered by status)."""
    items, total = await use_case.execute(status_filter, limit, offset)
    return Page[RunDTO](items=items, total=total, limit=limit, offset=offset)


@router.post("", response_model=RunDTO, status_code=status.HTTP_202_ACCEPTED)
async def trigger_refresh(
    body: TriggerRefreshRequest,
    background_tasks: BackgroundTasks,
    response: Response,
    create: Annotated[TriggerRefresh, Depends(get_trigger_refresh)],
    fetch: Annotated[GetRun, Depends(get_get_run)],
) -> RunDTO:
    """Create a run and screen stored data, optionally using an enabled data adapter."""
    _require_downloads_if_forced(body.force)
    triggered = await create.execute(body.strategy, body.force)
    if triggered.should_execute:
        background_tasks.add_task(
            run_screening_pipeline,
            body.strategy,
            force=body.force,
            run_id=triggered.run_id,
        )
    else:
        response.status_code = status.HTTP_200_OK
    return await fetch.execute(triggered.run_id)


@router.post("/execute", response_model=RunDTO)
async def execute_screening(
    body: TriggerRefreshRequest,
    background_tasks: BackgroundTasks,
    response: Response,
    execute: Annotated[ExecuteScreening, Depends(get_execute_screening)],
    create: Annotated[TriggerRefresh, Depends(get_trigger_refresh)],
    fetch: Annotated[GetRun, Depends(get_get_run)],
) -> RunDTO:
    """Execute the full end-to-end screening pipeline.

    By default, screens locally stored bars, computes indicators, runs the
    strategy engine, and persists scores and rankings. Direct exchange fetches
    require operator opt-in. ``force=true`` is rejected unless downloads are
    enabled.

    Default (``background=true``): creates a ``PENDING`` run and returns it
    immediately (``202``); the pipeline runs after the response is sent and
    the caller polls ``GET /runs/{id}`` for completion. A synchronous
    A synchronous full-universe screen can exceed ordinary gateway timeouts.

    ``background=false``: blocks and returns the ``COMPLETED`` run directly
    (``201``), matching the pre-Phase-1.6 behaviour -- used by tests and the
    CLI, which have no timeout to exceed.
    """
    if body.background:
        _require_downloads_if_forced(body.force)
        triggered = await create.execute(body.strategy, body.force)
        if triggered.should_execute:
            background_tasks.add_task(
                run_screening_pipeline,
                body.strategy,
                force=body.force,
                run_id=triggered.run_id,
            )
            response.status_code = status.HTTP_202_ACCEPTED
        else:
            response.status_code = status.HTTP_200_OK
        return await fetch.execute(triggered.run_id)

    _require_downloads_if_forced(body.force)
    run_id = await execute.execute(
        strategy_name=body.strategy,
        target_symbols=None,
        force=body.force,
    )
    response.status_code = status.HTTP_201_CREATED
    return await fetch.execute(run_id)


@router.get("/latest", response_model=RunDTO | None)
async def get_latest_run_for_strategy(
    use_case: Annotated[GetLatestRunForStrategy, Depends(get_get_latest_run_for_strategy)],
    strategy: Annotated[str, Query()] = "minervini_trend_template",
) -> RunDTO | None:
    """Return the latest completed run for a strategy (e.g. a Momentum Horizon)."""
    return await use_case.execute(strategy)


@router.get("/{run_id}", response_model=RunDTO)
async def get_run(
    run_id: int,
    use_case: Annotated[GetRun, Depends(get_get_run)],
) -> RunDTO:
    """Return a single run's status and stats."""
    return await use_case.execute(run_id)
