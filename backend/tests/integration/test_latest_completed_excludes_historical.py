"""Regression test: latest_completed() must resolve to the live run, not a backfill.

P0 discovered 2026-07-03 after RP-013 (historical screening-layer backfill).
The Live Dashboard resolves each Momentum Horizon's "latest run" through
``SqlScreeningRunRepository.latest_completed``. That method ordered by run_date
without excluding ``historical:%`` (or ``:research:``/``:icv2:``) runs -- the
opposite of ``list_runs`` -- so once RP-013 wrote historical backfill runs under
a strategy, the dashboard could surface an as-of-history snapshot as the current
live result. This asserts the live run always wins and a strategy with only
historical/research runs correctly reports no live run (None) rather than a
mislabeled backfill row.
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


async def _make_strategy(db_session: AsyncSession, name: str) -> int:
    strategy_repo = SqlStrategyRepository(db_session)
    strategy_id = await strategy_repo.upsert(
        Strategy(
            name=name,
            version=1,
            config_hash="abc",
            config=StrategyConfig(
                name=name,
                version=1,
                engines=(EngineConfig(id="trend_template", enabled=True, weight=Decimal("1")),),
            ),
        )
    )
    await db_session.commit()
    return strategy_id


@pytest.mark.asyncio
async def test_latest_completed_prefers_live_over_newer_dated_historical(
    db_session: AsyncSession,
) -> None:
    strategy_id = await _make_strategy(db_session, "latest_completed_live_wins_strategy")
    repo = SqlScreeningRunRepository(db_session)

    live_id = await _create_run(repo, strategy_id, date(2024, 1, 1), "2024-01-01")
    # A historical backfill row dated *after* the live run must not win.
    await _create_run(repo, strategy_id, date(2024, 6, 1), "historical:2024-06-01:1")
    await _create_run(repo, strategy_id, date(2024, 7, 1), "historical:2024-07-01:research:x")
    await db_session.commit()

    latest = await repo.latest_completed(strategy_id)
    assert latest is not None
    assert latest.id == live_id


@pytest.mark.asyncio
async def test_latest_completed_returns_none_when_only_historical(
    db_session: AsyncSession,
) -> None:
    strategy_id = await _make_strategy(db_session, "latest_completed_only_historical_strategy")
    repo = SqlScreeningRunRepository(db_session)

    await _create_run(repo, strategy_id, date(2024, 1, 1), "historical:2024-01-01:1")
    await _create_run(repo, strategy_id, date(2024, 2, 1), "historical:2024-02-01:icv2:9")
    await db_session.commit()

    assert await repo.latest_completed(strategy_id) is None
