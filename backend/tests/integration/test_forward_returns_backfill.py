"""Integration tests for ForwardReturnsBackfill (Objective 4, Research Feature Store)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.application.use_cases.research.forward_returns_backfill import (
    ForwardReturnsBackfill,
)
from momentum25.domain.entities.market_data import OHLCVBar
from momentum25.domain.ports.market_data import RawIndexBar
from momentum25.domain.research.forward_returns import LEGACY_HORIZON_BASIS
from momentum25.domain.value_objects.types import RunStatus, RunTrigger
from momentum25.infrastructure.calendar.nse_calendar import get_nse_trading_calendar
from momentum25.infrastructure.persistence.models import (
    ForwardReturnModel,
    ScreeningResultModel,
    ScreeningRunModel,
    SecurityModel,
    StrategyModel,
)
from momentum25.infrastructure.persistence.repositories.benchmark_index import (
    SqlBenchmarkIndexRepository,
)
from momentum25.infrastructure.persistence.repositories.ohlcv import SqlOHLCVRepository
from momentum25.infrastructure.persistence.repositories.screening_run import (
    SqlScreeningRunRepository,
)


def _next_sessions(after: date, count: int) -> list[date]:
    return get_nse_trading_calendar().sessions_between(
        after + timedelta(days=1), after + timedelta(days=30)
    )[:count]


async def _seed_run_with_result(session: AsyncSession, run_date: date) -> tuple[int, int]:
    """Seed a strategy, security, completed run, and one screening_result row."""
    strategy = StrategyModel(
        name="test_strategy", version=1, config={}, config_hash="hash", is_active=True
    )
    session.add(strategy)
    await session.flush()

    security = SecurityModel(symbol="TESTCO", name="Test Co", is_active=True)
    session.add(security)
    await session.flush()

    run = ScreeningRunModel(
        strategy_id=strategy.id,
        run_date=run_date,
        data_version="test",
        config_hash="hash",
        status=RunStatus.COMPLETED.value,
        trigger=RunTrigger.MANUAL.value,
    )
    session.add(run)
    await session.flush()

    session.add(
        ScreeningResultModel(
            run_id=run.id,
            security_id=security.id,
            rank=1,
            momentum_score=Decimal("50"),
            buy_setup_score=Decimal("50"),
            hard_filters_passed=True,
        )
    )
    await session.commit()
    return run.id, security.id


@pytest.mark.asyncio
async def test_backfill_computes_only_horizons_with_enough_forward_bars(
    db_session: AsyncSession,
) -> None:
    """Only horizons whose forward bars fully exist must be written."""
    run_date = date(2024, 1, 1)
    run_id, security_id = await _seed_run_with_result(db_session, run_date)

    ohlcv_repo = SqlOHLCVRepository(db_session)
    # Entry bar on run_date.
    await ohlcv_repo.upsert_bars(
        security_id,
        [
            OHLCVBar(
                date=run_date, open=Decimal("100"), high=Decimal("100"),
                low=Decimal("100"), close=Decimal("100"), volume=1000,
            )
        ],
    )
    # Bars on the next 5 NSE sessions -- market data reaches the 5-session
    # exit, not the 10-session one (R3-B-32: horizons count sessions).
    forward_bars = [
        OHLCVBar(
            date=day,
            open=Decimal("110"), high=Decimal("110"),
            low=Decimal("110"), close=Decimal("110"), volume=1000,
        )
        for day in _next_sessions(run_date, 5)
    ]
    await ohlcv_repo.upsert_bars(security_id, forward_bars)
    await db_session.commit()

    backfill = ForwardReturnsBackfill(
        screening_run_repo=SqlScreeningRunRepository(db_session),
        ohlcv_repo=ohlcv_repo,
        horizons=(5, 10),
        calendar=get_nse_trading_calendar(),
    )
    summary = await backfill.execute(run_id)
    assert summary["rows_written"] == 1  # only the 5-day horizon qualifies

    run_repo = SqlScreeningRunRepository(db_session)
    rows = await run_repo.get_forward_returns(run_id)
    assert len(rows) == 1
    assert rows[0].horizon_days == 5
    assert rows[0].forward_return == Decimal("0.1")  # (110/100) - 1
    assert rows[0].horizon_basis == "sessions"
    assert rows[0].exit_date == forward_bars[-1].date
    assert rows[0].exit_stale_sessions == 0


@pytest.mark.asyncio
async def test_backfill_is_idempotent_and_never_duplicates_rows(
    db_session: AsyncSession,
) -> None:
    """Re-running the backfill for an already-computed horizon must not duplicate it."""
    run_date = date(2024, 2, 1)
    run_id, security_id = await _seed_run_with_result(db_session, run_date)

    ohlcv_repo = SqlOHLCVRepository(db_session)
    await ohlcv_repo.upsert_bars(
        security_id,
        [
            OHLCVBar(
                date=run_date, open=Decimal("50"), high=Decimal("50"),
                low=Decimal("50"), close=Decimal("50"), volume=1000,
            ),
            OHLCVBar(
                date=run_date + timedelta(days=1), open=Decimal("55"), high=Decimal("55"),
                low=Decimal("55"), close=Decimal("55"), volume=1000,
            ),
        ],
    )
    await db_session.commit()

    backfill = ForwardReturnsBackfill(
        screening_run_repo=SqlScreeningRunRepository(db_session),
        ohlcv_repo=ohlcv_repo,
        horizons=(1,),
        calendar=get_nse_trading_calendar(),
    )
    first = await backfill.execute(run_id)
    second = await backfill.execute(run_id)

    assert first["rows_written"] == 1
    assert second["rows_written"] == 0  # already computed -- nothing new to write

    run_repo = SqlScreeningRunRepository(db_session)
    rows = await run_repo.get_forward_returns(run_id)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_backfill_computes_benchmark_relative_return_when_repo_supplied(
    db_session: AsyncSession,
) -> None:
    """When a benchmark_index_repo is supplied, excess_return must be computed."""
    run_date = date(2024, 3, 1)
    run_id, security_id = await _seed_run_with_result(db_session, run_date)

    ohlcv_repo = SqlOHLCVRepository(db_session)
    await ohlcv_repo.upsert_bars(
        security_id,
        [
            OHLCVBar(
                date=run_date, open=Decimal("100"), high=Decimal("100"),
                low=Decimal("100"), close=Decimal("100"), volume=1000,
            ),
            OHLCVBar(
                date=_next_sessions(run_date, 1)[0], open=Decimal("110"), high=Decimal("110"),
                low=Decimal("110"), close=Decimal("110"), volume=1000,
            ),
        ],
    )
    await db_session.commit()

    benchmark_repo = SqlBenchmarkIndexRepository(db_session)
    await benchmark_repo.upsert_bars(
        "NIFTY500",
        [
            RawIndexBar(index_code="NIFTY500", date=run_date, close=Decimal("20000")),
            RawIndexBar(
                index_code="NIFTY500",
                date=_next_sessions(run_date, 1)[0],
                close=Decimal("20200"),
            ),
        ],
    )
    await db_session.commit()

    backfill = ForwardReturnsBackfill(
        screening_run_repo=SqlScreeningRunRepository(db_session),
        ohlcv_repo=ohlcv_repo,
        benchmark_index_repo=benchmark_repo,
        horizons=(1,),
        calendar=get_nse_trading_calendar(),
    )
    await backfill.execute(run_id)

    run_repo = SqlScreeningRunRepository(db_session)
    rows = await run_repo.get_forward_returns(run_id)
    assert len(rows) == 1
    assert rows[0].forward_return == Decimal("0.10")  # (110/100) - 1
    assert rows[0].benchmark_return == Decimal("0.01")  # (20200/20000) - 1
    assert rows[0].excess_return == Decimal("0.09")  # 0.10 - 0.01


@pytest.mark.asyncio
async def test_legacy_rows_are_kept_and_never_mixed_with_session_rows(
    db_session: AsyncSession,
) -> None:
    """R3-B-32: an own-bars row stays as stored; readers see one basis at a time."""
    run_date = date(2024, 4, 1)
    run_id, security_id = await _seed_run_with_result(db_session, run_date)
    db_session.add(
        ForwardReturnModel(
            run_id=run_id,
            security_id=security_id,
            horizon_days=1,
            horizon_basis=LEGACY_HORIZON_BASIS,
            forward_return=Decimal("0.5"),
            forward_max_drawdown=Decimal(0),
            forward_volatility=Decimal(0),
        )
    )
    ohlcv_repo = SqlOHLCVRepository(db_session)
    await ohlcv_repo.upsert_bars(
        security_id,
        [
            OHLCVBar(
                date=day, open=Decimal(p), high=Decimal(p), low=Decimal(p),
                close=Decimal(p), volume=1000,
            )
            for day, p in ((run_date, "100"), (_next_sessions(run_date, 1)[0], "104"))
        ],
    )
    await db_session.commit()

    backfill = ForwardReturnsBackfill(
        screening_run_repo=SqlScreeningRunRepository(db_session),
        ohlcv_repo=ohlcv_repo,
        horizons=(1,),
        calendar=get_nse_trading_calendar(),
    )
    assert (await backfill.execute(run_id))["rows_written"] == 1

    run_repo = SqlScreeningRunRepository(db_session)
    [current] = await run_repo.get_forward_returns(run_id)
    [legacy] = await run_repo.get_forward_returns(run_id, basis=LEGACY_HORIZON_BASIS)
    assert current.forward_return == Decimal("0.04")
    assert legacy.forward_return == Decimal("0.5")  # untouched
    assert await run_repo.get_forward_return_by_security(run_id, 1) == {
        security_id: Decimal("0.04")
    }
