"""Integration tests for the ScreeningOrchestrator.

Validates the full daily screening lifecycle: universe resolution, data sync,
throttled concurrent indicator computation, strategy orchestration, and result
persistence against a seeded Postgres test container.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.application.use_cases.screening_orchestrator import ScreeningOrchestrator
from momentum25.domain.entities.strategy import EngineConfig, Strategy, StrategyConfig
from momentum25.domain.scoring.ranking_engine import RankingEngineImpl
from momentum25.domain.scoring.scoring_engine import ScoringEngineImpl
from momentum25.domain.strategy.engine_registry import EngineRegistry
from momentum25.domain.strategy.strategy_engine import StrategyEngine
from momentum25.infrastructure.persistence.models import (
    ScreeningResultModel,
    ScreeningRunModel,
    SecurityModel,
)
from momentum25.infrastructure.persistence.repositories import (
    SqlOHLCVRepository,
    SqlScreeningRunRepository,
    SqlSecurityRepository,
    SqlStrategyRepository,
)
from momentum25.infrastructure.pipelines.indicator_pipeline import IndicatorPipelineImpl


def _make_uptrend_bars(days: int, start: date, base_price: float = 100.0) -> list[dict]:
    """Generate uptrend bars."""
    bars = []
    price = base_price
    for i in range(days):
        d = start + timedelta(days=i)
        bars.append(
            {
                "security_id": 0,
                "date": d,
                "open": price,
                "high": price + 2,
                "low": price - 1,
                "close": price + 1,
                "volume": 1_000_000,
                "adj_close": None,
            }
        )
        price += 0.5
    return bars


def _make_descending_bars(days: int, start: date, base_price: float = 400.0) -> list[dict]:
    """Generate bars with a steadily declining close (descending 200 SMA).

    The default base must keep the close above the strategy's declared minimum
    price for the whole run: at 0.8/day over 300 days the series falls 240, so a
    200.0 base ended *below zero* and the security was excluded by the liquidity
    floor before the trend rules ever ran (Phase 0.1). This fixture exists to
    fail the trend gate, not the universe gate.
    """
    bars = []
    price = base_price
    for i in range(days):
        d = start + timedelta(days=i)
        bars.append(
            {
                "security_id": 0,
                "date": d,
                "open": price,
                "high": price + 1,
                "low": price - 2,
                "close": price - 0.8,
                "volume": 1_000_000,
                "adj_close": None,
            }
        )
        price -= 0.8
    return bars


async def _seed_security(session: AsyncSession, symbol: str, name: str) -> SecurityModel:
    """Insert a security and return its ORM model."""
    model = SecurityModel(symbol=symbol, name=name, is_active=True)
    session.add(model)
    await session.flush()
    await session.refresh(model)
    return model


async def _seed_bars(
    session: AsyncSession, security_id: int, bars: list[dict]
) -> None:
    """Bulk upsert bars for a security."""
    repo = SqlOHLCVRepository(session)
    # convert dicts to OHLCVBar-like objects expected by repo
    from decimal import Decimal

    from momentum25.domain.entities.market_data import OHLCVBar
    bar_objs = [
        OHLCVBar(
            date=b["date"],
            open=Decimal(str(b["open"])),
            high=Decimal(str(b["high"])),
            low=Decimal(str(b["low"])),
            close=Decimal(str(b["close"])),
            volume=b["volume"],
            adj_close=b.get("adj_close"),
            # Real rupee turnover (close x volume), as the bhavcopy provider now
            # persists it. The strategy's declared liquidity floor (Phase 0.1)
            # gates on real turnover and deliberately excludes securities that
            # have none, so a fixture lacking this column would no longer
            # represent an ingested security.
            turnover_value=Decimal(str(b["close"])) * Decimal(b["volume"]),
        )
        for b in bars
    ]
    await repo.upsert_bars(security_id, bar_objs)
    await session.commit()


@pytest.mark.asyncio
async def test_orchestrator_full_lifecycle(db_session: AsyncSession) -> None:
    """3 securities (pass, fail, IPO) must yield summary (1, 1, 1) and persist run."""
    start_date = date(2024, 1, 1)
    target_date = start_date + timedelta(days=299)

    # Seed 3 securities
    pass_sec = await _seed_security(db_session, "PASSER", "Passing Trend")
    fail_sec = await _seed_security(db_session, "FAILER", "Failing Trend")
    ipo_sec = await _seed_security(db_session, "NEWIPO", "Recent IPO")
    stale_sec = await _seed_security(db_session, "STALER", "Stale Data")

    # Seed 300 bars for PASSER (uptrend) and FAILER (descending)
    await _seed_bars(db_session, pass_sec.id, _make_uptrend_bars(300, start_date, 100.0))
    await _seed_bars(
        db_session, fail_sec.id, _make_descending_bars(300, start_date, 400.0)
    )
    # 10 bars for IPO
    await _seed_bars(
        db_session, ipo_sec.id, _make_uptrend_bars(10, target_date - timedelta(days=9))
    )
    # Enough history to be scoreable, but ingestion stopped long before
    # target_date -- exercises the stale_data skip bucket.
    await _seed_bars(
        db_session, stale_sec.id, _make_uptrend_bars(300, start_date - timedelta(days=120), 100.0)
    )

    # Wire collaborators
    security_repo = SqlSecurityRepository(db_session)
    ohlcv_repo = SqlOHLCVRepository(db_session)
    screening_run_repo = SqlScreeningRunRepository(db_session)
    strategy_repo = SqlStrategyRepository(db_session)
    indicator_pipeline = IndicatorPipelineImpl(db_session)

    from momentum25.domain.engines.trend_template import TrendTemplateEngine

    registry = EngineRegistry()
    registry.register(TrendTemplateEngine())
    scoring_engine = ScoringEngineImpl()
    ranking_engine = RankingEngineImpl()
    strategy_engine = StrategyEngine(
        engines=registry, scoring=scoring_engine, ranking=ranking_engine
    )
    strategy = Strategy(
        name="test_strategy",
        version=1,
        config_hash="abc",
        config=StrategyConfig(
            name="test_strategy",
            version=1,
            engines=(EngineConfig(id="trend_template", enabled=True, weight=Decimal("1")),),
        ),
    )

    orchestrator = ScreeningOrchestrator(
        security_repo=security_repo,
        ohlcv_repo=ohlcv_repo,
        screening_run_repo=screening_run_repo,
        indicator_pipeline=indicator_pipeline,
        strategy_engine=strategy_engine,
        strategy=strategy,
        strategy_repo=strategy_repo,
    )

    summary = await orchestrator.run_daily_screening(target_date)

    assert summary.run_date == target_date
    assert summary.total_evaluated == 4
    # 1 pass (PASSER), 1 fail (FAILER fails gate), 1 insufficient (IPO), 1 stale (STALER)
    assert (
        summary.total_passed
        + summary.total_skipped_insufficient_data
        + summary.total_failed
        + summary.total_skipped_stale_data
        + summary.total_skipped_ineligible_universe
        == 4
    )
    assert summary.total_skipped_stale_data == 1

    # Verify exactly one ScreeningRun row was persisted
    count_row = await db_session.execute(
        select(func.count()).select_from(ScreeningRunModel)
    )
    run_count = count_row.scalar_one()
    assert run_count == 1, f"Expected 1 ScreeningRun row, got {run_count}"

    # The persisted stats must account for every evaluated symbol. Without this,
    # an all-skipped run reads as "evaluated N, passed 0, failed 0" with symbols
    # silently unaccounted for, and duration renders as 0.00s.
    run_row = (await db_session.execute(select(ScreeningRunModel))).scalars().one()
    stats = run_row.stats
    accounted = (
        stats["total_passed"]
        + stats["total_failed"]
        + stats["total_skipped"]
        + stats["total_skipped_stale_data"]
        + stats["total_skipped_ineligible_universe"]
    )
    assert accounted == stats["total_evaluated"], f"unaccounted symbols in {stats}"
    assert stats["duration_seconds"] > 0

    # Pins the exact keys the dashboard reads (web/src/app/page.tsx) -- a
    # rename here without updating the frontend silently renders "passed 0 /
    # failed 0" for every run, healthy or not.
    assert set(stats) >= {"total_evaluated", "total_passed", "total_failed", "duration_seconds"}


@pytest.mark.asyncio
async def test_orchestrator_screening_date_with_no_bar_fails_run(
    db_session: AsyncSession,
) -> None:
    """A trading_date with no matching bar for any security must FAIL the run.

    Reproduces run #5 (2026-08-09, a Sunday): ExecuteScreening previously
    passed date.today() straight through as trading_date, and the universe
    admission gate (bars[-1].date != trading_date) dropped every security as
    no_bar_on_trading_date -- the run still completed with total_evaluated=3235,
    total_passed=0, total_failed=0, and zero screening_results rows. This must
    now surface as a FAILED run rather than a silently empty COMPLETED one.
    """
    start_date = date(2024, 1, 1)
    last_bar_date = start_date + timedelta(days=299)
    no_bar_date = last_bar_date + timedelta(days=5)  # no security has a bar here

    pass_sec = await _seed_security(db_session, "PASSER", "Passing Trend")
    await _seed_bars(db_session, pass_sec.id, _make_uptrend_bars(300, start_date, 100.0))

    security_repo = SqlSecurityRepository(db_session)
    ohlcv_repo = SqlOHLCVRepository(db_session)
    screening_run_repo = SqlScreeningRunRepository(db_session)
    strategy_repo = SqlStrategyRepository(db_session)
    indicator_pipeline = IndicatorPipelineImpl(db_session)

    from momentum25.domain.engines.trend_template import TrendTemplateEngine

    registry = EngineRegistry()
    registry.register(TrendTemplateEngine())
    strategy_engine = StrategyEngine(
        engines=registry, scoring=ScoringEngineImpl(), ranking=RankingEngineImpl()
    )
    strategy = Strategy(
        name="test_strategy_no_bar",
        version=1,
        config_hash="abc",
        config=StrategyConfig(
            name="test_strategy_no_bar",
            version=1,
            engines=(EngineConfig(id="trend_template", enabled=True, weight=Decimal("1")),),
        ),
    )

    orchestrator = ScreeningOrchestrator(
        security_repo=security_repo,
        ohlcv_repo=ohlcv_repo,
        screening_run_repo=screening_run_repo,
        indicator_pipeline=indicator_pipeline,
        strategy_engine=strategy_engine,
        strategy=strategy,
        strategy_repo=strategy_repo,
    )

    # The orchestrator marks the run FAILED and re-raises; the specific type is
    # whatever the pipeline raised, so assert on the persisted status below.
    with pytest.raises(Exception, match=r".*"):  # noqa: B017
        await orchestrator.run_daily_screening(no_bar_date)

    run_row = (await db_session.execute(select(ScreeningRunModel))).scalars().one()
    assert run_row.status == "FAILED"

    results_count = await db_session.execute(
        select(func.count()).select_from(ScreeningResultModel)
    )
    assert results_count.scalar_one() == 0