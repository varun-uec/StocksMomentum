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

The same defect class was found in ``score_history`` and
``get_previous_run_ranks`` by the 2026-08-15 functional audit (F5, F13): both
read every completed run for a strategy, so a historical backfill could supply
a security's prior rank or duplicate a date in its score history. Those runs
now share one ``_LIVE_RUN_PREDICATES`` definition, and the tests below pin it.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.entities.run import RunStatus, RunTrigger, ScreeningRun
from momentum25.domain.entities.strategy import EngineConfig, Strategy, StrategyConfig
from momentum25.domain.value_objects.results import Ranking, StockScore
from momentum25.infrastructure.persistence.models import SecurityModel
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


async def _seed_security(db_session: AsyncSession, symbol: str) -> int:
    model = SecurityModel(symbol=symbol, name=symbol, is_active=True)
    db_session.add(model)
    await db_session.flush()
    await db_session.refresh(model)
    return int(model.id)


async def _save_score(
    repo: SqlScreeningRunRepository, run_id: int, security_id: int, score: str, rank: int
) -> None:
    await repo.save_results(
        run_id,
        [
            StockScore(
                security_id=security_id,
                momentum_score=Decimal(score),
                buy_setup_score=Decimal(score),
                engine_results=(),
                hard_filters_passed=True,
            )
        ],
        [
            Ranking(
                security_id=security_id,
                momentum_score=Decimal(score),
                buy_setup_score=Decimal(score),
                rank=rank,
            )
        ],
    )


@pytest.mark.asyncio
async def test_score_history_returns_one_live_point_per_run_date(
    db_session: AsyncSession,
) -> None:
    """F5/F13: history must exclude historical runs and collapse re-run dates.

    Three completed runs share 2024-01-01: a live run, a re-run of that same
    live date, and a historical backfill. History must show that date once,
    with the newest live run's score.
    """
    strategy_id = await _make_strategy(db_session, "score_history_dedup_strategy")
    repo = SqlScreeningRunRepository(db_session)
    security_id = await _seed_security(db_session, "HISTDEDUP")

    first = await _create_run(repo, strategy_id, date(2024, 1, 1), "2024-01-01")
    rerun = await _create_run(repo, strategy_id, date(2024, 1, 1), "2024-01-01:rerun")
    backfill = await _create_run(repo, strategy_id, date(2024, 1, 1), "historical:2024-01-01:1")
    earlier = await _create_run(repo, strategy_id, date(2023, 12, 29), "2023-12-29")

    await _save_score(repo, first, security_id, "10", 5)
    await _save_score(repo, rerun, security_id, "20", 4)
    await _save_score(repo, backfill, security_id, "99", 1)
    await _save_score(repo, earlier, security_id, "30", 3)
    await db_session.commit()

    points = await repo.score_history(strategy_id, security_id, limit=90)

    assert [p.run_date for p in points] == [date(2024, 1, 1), date(2023, 12, 29)]
    # The newest *live* run for the shared date wins; the backfill's 99 is gone.
    assert points[0].momentum_score == Decimal("20.0000")


@pytest.mark.asyncio
async def test_previous_run_ranks_skips_historical_runs(db_session: AsyncSession) -> None:
    """F13: rank change must compare against the prior *live* run."""
    strategy_id = await _make_strategy(db_session, "prev_ranks_live_only_strategy")
    repo = SqlScreeningRunRepository(db_session)
    security_id = await _seed_security(db_session, "PREVRANK")

    live_prior = await _create_run(repo, strategy_id, date(2024, 1, 1), "2024-01-01")
    backfill = await _create_run(repo, strategy_id, date(2024, 1, 2), "historical:2024-01-02:1")
    current = await _create_run(repo, strategy_id, date(2024, 1, 3), "2024-01-03")

    await _save_score(repo, live_prior, security_id, "10", 7)
    await _save_score(repo, backfill, security_id, "99", 1)
    await _save_score(repo, current, security_id, "20", 2)
    await db_session.commit()

    ranks = await repo.get_previous_run_ranks(strategy_id, current, date(2024, 1, 3))

    assert ranks == {security_id: 7}
