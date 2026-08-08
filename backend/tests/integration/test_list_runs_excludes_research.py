"""Regression test: list_runs() must exclude research/experimental runs by default.

Discovered live on 2026-07-02: an 81-run Ranking-IC re-measurement walk-forward
was tagged under the active production strategy and, once created, permanently
inflated every product-facing aggregate query (scorecard, alpha analysis,
rule/engine effectiveness -- all backing the /validation dashboard), pushing
its load time from ~13-17s to ~26.5s, enough to trip a 20s page-load timeout.
The runs are real and permanent (ADR-006 append-only, cannot be deleted), so
the fix is at the query layer: exclude them from product-facing queries by
default while keeping them directly queryable for research.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.entities.run import RunStatus, RunTrigger, ScreeningRun
from momentum25.domain.entities.strategy import EngineConfig, Strategy, StrategyConfig
from momentum25.infrastructure.persistence.repositories import (
    SqlScreeningRunRepository,
    SqlStrategyRepository,
)


async def _create_run(
    repo: SqlScreeningRunRepository, strategy_id: int, run_date: date, data_version: str
) -> int:
    run = ScreeningRun(
        strategy_id=strategy_id,
        run_date=run_date,
        data_version=data_version,
        config_hash="abc",
        trigger=RunTrigger.MANUAL,
        status=RunStatus.RUNNING,
    )
    run_id = await repo.create(run)
    run.id = run_id
    run.status = RunStatus.COMPLETED
    await repo.update(run)
    return run_id


@pytest.mark.asyncio
async def test_list_runs_excludes_research_tagged_runs_by_default(
    db_session: AsyncSession,
) -> None:
    strategy_repo = SqlStrategyRepository(db_session)
    strategy_id = await strategy_repo.upsert(
        Strategy(
            name="list_runs_research_test_strategy",
            version=1,
            config_hash="abc",
            config=StrategyConfig(
                name="list_runs_research_test_strategy",
                version=1,
                engines=(EngineConfig(id="trend_template", enabled=True, weight=Decimal("1")),),
            ),
        )
    )
    await db_session.commit()

    repo = SqlScreeningRunRepository(db_session)

    real_id = await _create_run(repo, strategy_id, date(2024, 1, 1), "historical:2024-01-01:a")
    icv2_id = await _create_run(
        repo, strategy_id, date(2024, 1, 2), "historical:2024-01-02:icv2:1234567890"
    )
    research_id = await _create_run(
        repo, strategy_id, date(2024, 1, 3), "historical:2024-01-03:research:experiment_x"
    )
    await db_session.commit()

    runs, total = await repo.list_runs(
        status="COMPLETED", limit=100, offset=0, exclude_historical=False
    )
    ids = {r.id for r in runs}

    assert real_id in ids
    assert icv2_id not in ids
    assert research_id not in ids

    # Explicitly opting in still finds them -- the data is real and permanent,
    # just not surfaced to product-facing aggregate queries by default.
    all_runs, all_total = await repo.list_runs(
        status="COMPLETED",
        limit=100,
        offset=0,
        exclude_historical=False,
        exclude_research=False,
    )
    all_ids = {r.id for r in all_runs}
    assert {real_id, icv2_id, research_id} <= all_ids
