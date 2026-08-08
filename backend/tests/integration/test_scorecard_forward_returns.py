"""Regression test: StrategyScorecardUseCase must use real forward returns.

Previously ``period_returns`` was built from each run's *average momentum
score* (a 0-100 quality rating) and fed directly into ``compute_scorecard``'s
compounding math as if it were a fractional period return -- summing ~36
"percent" per run across 165 runs produced a multi-million-percent CAGR.
This test proves the fix: period returns must come from the Top 25 picks'
persisted forward returns, runs without a matured forward window are
skipped (never fabricated), and duplicate runs on the same date are
collapsed to one.

Runs and rankings are built directly via the repository rather than through
the full screening pipeline: qualification depends on TrendTemplateEngine's
indicator thresholds, which are orthogonal to what this test verifies
(the scorecard's return computation, not stock selection).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.application.use_cases.validation import StrategyScorecardUseCase
from momentum25.domain.entities.run import RunStatus, RunTrigger, ScreeningRun
from momentum25.domain.entities.strategy import EngineConfig, Strategy, StrategyConfig
from momentum25.domain.research.forward_returns import ForwardReturn
from momentum25.domain.value_objects.results import Ranking, StockScore
from momentum25.infrastructure.persistence.models import SecurityModel
from momentum25.infrastructure.persistence.repositories import (
    SqlScreeningRunRepository,
    SqlStrategyRepository,
)


async def _seed_strategy(strategy_repo: SqlStrategyRepository, name: str) -> Strategy:
    strategy = Strategy(
        name=name,
        version=1,
        config_hash="abc",
        config=StrategyConfig(
            name=name,
            version=1,
            engines=(EngineConfig(id="trend_template", enabled=True, weight=Decimal("1")),),
        ),
    )
    await strategy_repo.upsert(strategy)
    return strategy


async def _create_completed_run(
    run_repo: SqlScreeningRunRepository,
    strategy: Strategy,
    run_date: date,
    security_id: int,
    data_version_suffix: str,
) -> int:
    run = ScreeningRun(
        strategy_id=strategy.id or 0,
        run_date=run_date,
        data_version=f"historical:{run_date.isoformat()}:{data_version_suffix}",
        config_hash=strategy.config_hash,
        trigger=RunTrigger.MANUAL,
        status=RunStatus.RUNNING,
    )
    run_id = await run_repo.create(run)

    score = StockScore(
        security_id=security_id,
        momentum_score=Decimal("62.5"),
        buy_setup_score=Decimal("70.0"),
        engine_results=(),
        hard_filters_passed=True,
    )
    ranking = Ranking(
        security_id=security_id,
        momentum_score=Decimal("62.5"),
        buy_setup_score=Decimal("70.0"),
        rank=1,
    )
    await run_repo.save_results(run_id, [score], [ranking])

    run.id = run_id
    run.status = RunStatus.COMPLETED
    run.finished_at = datetime.now(UTC)
    run.stats = {"total_evaluated": 1, "total_passed": 1, "total_failed": 0}
    await run_repo.update(run)
    return run_id


@pytest.mark.asyncio
async def test_scorecard_uses_forward_returns_not_momentum_score(
    db_session: AsyncSession,
) -> None:
    security = SecurityModel(symbol="SCFWD", name="Scorecard Forward Co", is_active=True)
    db_session.add(security)
    await db_session.flush()
    await db_session.refresh(security)
    await db_session.commit()

    strategy_repo = SqlStrategyRepository(db_session)
    strategy = await _seed_strategy(strategy_repo, "scorecard_fwd_strategy")
    await db_session.commit()

    run_repo = SqlScreeningRunRepository(db_session)
    strategy = await strategy_repo.get_active("scorecard_fwd_strategy")
    assert strategy is not None

    run1_id = await _create_completed_run(
        run_repo, strategy, date(2024, 1, 1), security.id, "a"
    )
    run2_id = await _create_completed_run(
        run_repo, strategy, date(2024, 2, 1), security.id, "b"
    )
    await db_session.commit()

    # Only run1 gets a matured 20-day forward return -- run2's window hasn't
    # matured yet and must be skipped, not fabricated.
    await run_repo.save_forward_returns(
        run1_id,
        [
            ForwardReturn(
                security_id=security.id,
                horizon_days=20,
                forward_return=Decimal("0.05"),
                forward_max_drawdown=Decimal("0.02"),
                forward_volatility=Decimal("0.01"),
                forward_mfe=Decimal("0.06"),
                forward_mae=Decimal("-0.01"),
            )
        ],
    )
    await db_session.commit()

    use_case = StrategyScorecardUseCase(
        screening_run_repo=run_repo,
        strategy_repo=strategy_repo,
    )
    scorecard = await use_case.execute("scorecard_fwd_strategy", max_runs=50)

    # Both runs are reported (total_runs), but only run1 contributes a period
    # return -- and it must be the persisted 5% forward return, not a
    # momentum score (62.5) compounded as if it were a percentage.
    assert scorecard.total_runs == 2
    assert scorecard.cumulative_return == Decimal("0.05")
    assert scorecard.best_return == Decimal("0.05")
    assert scorecard.cagr < Decimal("10")  # sane: not a multi-million-percent figure
    assert run2_id  # run2 was created but contributed no period return


@pytest.mark.asyncio
async def test_scorecard_dedupes_runs_on_same_date(db_session: AsyncSession) -> None:
    """Two runs on the same trading day must count as one period, not two."""
    security = SecurityModel(symbol="SCFWD2", name="Scorecard Forward Co 2", is_active=True)
    db_session.add(security)
    await db_session.flush()
    await db_session.refresh(security)
    await db_session.commit()

    strategy_repo = SqlStrategyRepository(db_session)
    await _seed_strategy(strategy_repo, "scorecard_dedup_strategy")
    await db_session.commit()

    run_repo = SqlScreeningRunRepository(db_session)
    strategy = await strategy_repo.get_active("scorecard_dedup_strategy")
    assert strategy is not None

    same_date = date(2024, 1, 1)
    await _create_completed_run(run_repo, strategy, same_date, security.id, "a")
    run_b_id = await _create_completed_run(run_repo, strategy, same_date, security.id, "b")
    await db_session.commit()

    # A forward return must exist for at least one of the two same-date runs,
    # otherwise compute_scorecard's n==0 branch reports total_runs=0
    # regardless of dedup correctness -- this isolates the dedup behavior
    # from the (separately tested) forward-return wiring.
    await run_repo.save_forward_returns(
        run_b_id,
        [
            ForwardReturn(
                security_id=security.id,
                horizon_days=20,
                forward_return=Decimal("0.03"),
                forward_max_drawdown=Decimal("0.01"),
                forward_volatility=Decimal("0.01"),
                forward_mfe=Decimal("0.04"),
                forward_mae=Decimal("-0.01"),
            )
        ],
    )
    await db_session.commit()

    use_case = StrategyScorecardUseCase(
        screening_run_repo=run_repo,
        strategy_repo=strategy_repo,
    )
    scorecard = await use_case.execute("scorecard_dedup_strategy", max_runs=50)

    assert scorecard.total_runs == 1
