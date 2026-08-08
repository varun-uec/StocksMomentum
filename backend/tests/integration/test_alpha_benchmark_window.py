"""Regression test: AlphaMeasurementUseCase must compare same-window returns.

Previously the benchmark side of alpha analysis used a single-day trailing
benchmark return (``BenchmarkIndexRepository.get_return``) compared against
the strategy's 20-trading-day forward return -- an apples-to-oranges window
mismatch that understated the benchmark by roughly 20x. This test proves the
fix: the benchmark return must come from the same forward-returns feature
store rows (same entry/exit dates) as the strategy return, not a separately
queried single-day return.

Also covers: only "NIFTY500" is reported (the only benchmark with ingested
history -- "NIFTY 50" was never ingested and must not appear as a fabricated
0% comparison).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.application.use_cases.validation import AlphaMeasurementUseCase
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
async def test_alpha_benchmark_return_uses_same_window_as_strategy_return(
    db_session: AsyncSession,
) -> None:
    security = SecurityModel(symbol="ALPHAWIN", name="Alpha Window Co", is_active=True)
    db_session.add(security)
    await db_session.flush()
    await db_session.refresh(security)
    await db_session.commit()

    strategy_repo = SqlStrategyRepository(db_session)
    await _seed_strategy(strategy_repo, "alpha_window_strategy")
    await db_session.commit()

    run_repo = SqlScreeningRunRepository(db_session)
    strategy = await strategy_repo.get_active("alpha_window_strategy")
    assert strategy is not None

    run_id = await _create_completed_run(
        run_repo, strategy, date(2024, 1, 1), security.id, "a"
    )
    await db_session.commit()

    # forward_return and benchmark_return both cover the same 20-trading-day
    # window (same entry/exit dates) -- exactly what the fix must use,
    # rather than a separately queried single-day trailing benchmark return.
    await run_repo.save_forward_returns(
        run_id,
        [
            ForwardReturn(
                security_id=security.id,
                horizon_days=20,
                forward_return=Decimal("0.05"),
                forward_max_drawdown=Decimal("0.02"),
                forward_volatility=Decimal("0.01"),
                forward_mfe=Decimal("0.06"),
                forward_mae=Decimal("-0.01"),
                benchmark_return=Decimal("0.03"),
                excess_return=Decimal("0.02"),
            )
        ],
    )
    await db_session.commit()

    use_case = AlphaMeasurementUseCase(
        screening_run_repo=run_repo,
        strategy_repo=strategy_repo,
    )
    report = await use_case.execute("alpha_window_strategy", max_runs=50)

    assert len(report.comparisons) == 1
    comparison = report.comparisons[0]
    assert comparison.benchmark_code == "NIFTY500"
    assert comparison.strategy_return == Decimal("0.05")
    assert comparison.benchmark_return == Decimal("0.03")
    assert comparison.alpha == Decimal("0.02")


@pytest.mark.asyncio
async def test_alpha_omits_nifty50_rather_than_fabricating_zero(
    db_session: AsyncSession,
) -> None:
    """NIFTY 50 has no ingested history -- it must not appear as a fake 0% comparison."""
    security = SecurityModel(symbol="ALPHAWIN2", name="Alpha Window Co 2", is_active=True)
    db_session.add(security)
    await db_session.flush()
    await db_session.refresh(security)
    await db_session.commit()

    strategy_repo = SqlStrategyRepository(db_session)
    await _seed_strategy(strategy_repo, "alpha_window_strategy_2")
    await db_session.commit()

    run_repo = SqlScreeningRunRepository(db_session)
    strategy = await strategy_repo.get_active("alpha_window_strategy_2")
    assert strategy is not None

    run_id = await _create_completed_run(
        run_repo, strategy, date(2024, 1, 1), security.id, "a"
    )
    await db_session.commit()
    await run_repo.save_forward_returns(
        run_id,
        [
            ForwardReturn(
                security_id=security.id,
                horizon_days=20,
                forward_return=Decimal("0.05"),
                forward_max_drawdown=Decimal("0.02"),
                forward_volatility=Decimal("0.01"),
                forward_mfe=Decimal("0.06"),
                forward_mae=Decimal("-0.01"),
                benchmark_return=Decimal("0.03"),
            )
        ],
    )
    await db_session.commit()

    use_case = AlphaMeasurementUseCase(
        screening_run_repo=run_repo,
        strategy_repo=strategy_repo,
    )
    report = await use_case.execute("alpha_window_strategy_2", max_runs=50)

    codes = {c.benchmark_code for c in report.comparisons}
    assert codes == {"NIFTY500"}
    assert "NIFTY_50" not in codes
    assert "NIFTY50" not in codes
