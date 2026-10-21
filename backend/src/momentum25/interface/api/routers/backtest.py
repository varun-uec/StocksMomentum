"""Walk-forward backtest API endpoint.

Exposes the ``walk-forward`` CLI command as an HTTP route. It changes nothing
about the backtest: same wiring, same providers, same frozen math (see
``momentum25.interface.walk_forward_wiring``).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from starlette.concurrency import run_in_threadpool

from momentum25.application.dto.walk_forward import (
    BacktestRequest,
    BacktestResponse,
    referenced_security_ids,
    to_backtest_response,
)
from momentum25.application.use_cases.walk_forward import WalkForwardRunner
from momentum25.domain.ports.repositories import SecurityRepository
from momentum25.domain.value_objects.manifest import DataManifest
from momentum25.infrastructure.persistence.repositories.walk_forward_market_data import (
    SURVIVORSHIP_ELIGIBILITY_WARNING,
)
from momentum25.interface.api.dependencies import get_security_repo
from momentum25.interface.walk_forward_wiring import build_walk_forward_runner

router = APIRouter(prefix="/backtest", tags=["backtest"])

RunnerFactory = Callable[[date, date], Awaitable[tuple[WalkForwardRunner, DataManifest]]]


def get_walk_forward_runner_factory() -> RunnerFactory:
    """Provide the factory that binds a runner to real Postgres data."""
    return build_walk_forward_runner


@router.post(
    "/walk-forward",
    response_model=BacktestResponse,
    summary="Run a walk-forward backtest",
    description="Run the monthly-rebalanced momentum backtest (execution method v2) over a "
    "date range against real point-in-time price, benchmark and survivorship data. "
    "The response carries the benchmark label next to the benchmark return and "
    "the survivorship/eligibility caveat; both must be shown wherever the "
    "numbers are shown.",
)
async def run_walk_forward(
    body: BacktestRequest,
    runner_factory: Annotated[RunnerFactory, Depends(get_walk_forward_runner_factory)],
    securities: Annotated[SecurityRepository, Depends(get_security_repo)],
) -> BacktestResponse:
    """Run the backtest over ``[start, end]`` and return its full log."""
    if body.start > body.end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="start must be on or before end",
        )
    runner, manifest = await runner_factory(body.start, body.end)
    # The run itself is synchronous, CPU-bound and can take seconds over a
    # multi-year range, so it must not block the event loop.
    result = await run_in_threadpool(
        runner.run, body.start, body.end, body.initial_capital
    )
    wanted = referenced_security_ids(result)
    symbols = {
        s.id: str(s.symbol)
        for s in await securities.list_all()
        if s.id is not None and s.id in wanted
    }
    return to_backtest_response(
        result, body.start, body.end, SURVIVORSHIP_ELIGIBILITY_WARNING, manifest, symbols
    )
