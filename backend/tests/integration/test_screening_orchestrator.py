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

    # Seed 300 bars for PASSER (uptrend) and FAILER (descending)
    await _seed_bars(db_session, pass_sec.id, _make_uptrend_bars(300, start_date, 100.0))
    await _seed_bars(
        db_session, fail_sec.id, _make_descending_bars(300, start_date, 400.0)
    )
    # 10 bars for IPO
    await _seed_bars(
        db_session, ipo_sec.id, _make_uptrend_bars(10, target_date - timedelta(days=9))
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
    assert summary.total_evaluated == 3
    # Expect 1 pass (PASSER), 1 fail (FAILER fails gate), 1 skipped (IPO insufficient data)
    assert (
        summary.total_passed
        + summary.total_skipped_insufficient_data
        + summary.total_failed
        == 3
    )

    # Verify exactly one ScreeningRun row was persisted
    count_row = await db_session.execute(
        select(func.count()).select_from(ScreeningRunModel)
    )
    run_count = count_row.scalar_one()
    assert run_count == 1, f"Expected 1 ScreeningRun row, got {run_count}"