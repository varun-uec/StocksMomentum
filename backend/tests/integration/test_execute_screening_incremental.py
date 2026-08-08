"""Integration tests for incremental + background ``/runs/execute`` (Phase 1.6).

Before this phase, ``ExecuteScreening`` fetched 501 sequential calendar days
on every call regardless of what was already persisted -- including every
weekend and holiday, each a full network round-trip returning nothing. These
tests prove: (a) a re-run only fetches sessions after the last persisted
bar, using the real NSE trading calendar to skip non-sessions, and (b) the
background execution path returns a run immediately and it reaches
COMPLETED asynchronously.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.app.services.screening_job import run_screening_pipeline
from momentum25.application.use_cases.screening import ExecuteScreening
from momentum25.domain.entities.strategy import EngineConfig, Strategy, StrategyConfig
from momentum25.domain.ports.market_data import RawBar, RawInstrument
from momentum25.domain.scoring.ranking_engine import RankingEngineImpl
from momentum25.domain.scoring.scoring_engine import ScoringEngineImpl
from momentum25.domain.strategy.engine_registry import EngineRegistry
from momentum25.domain.strategy.strategy_engine import StrategyEngine
from momentum25.domain.value_objects.types import RunStatus
from momentum25.infrastructure.calendar.nse_calendar import get_nse_trading_calendar
from momentum25.infrastructure.persistence.repositories import (
    SqlOHLCVRepository,
    SqlScreeningRunRepository,
    SqlSecurityRepository,
    SqlStrategyRepository,
)
from momentum25.infrastructure.pipelines.indicator_pipeline import IndicatorPipelineImpl


class _RecordingProvider:
    """Fake MarketDataProvider recording which dates were fetched."""

    def __init__(self, bars_by_date: dict[date, list[RawBar]]) -> None:
        self._bars_by_date = bars_by_date
        self.fetch_calls: list[date] = []

    async def fetch_eod_full(self, for_date: date) -> list[RawBar]:
        self.fetch_calls.append(for_date)
        return self._bars_by_date.get(for_date, [])

    async def fetch_instrument_master(self) -> list[RawInstrument]:
        return [RawInstrument(symbol="INCR", name="Incremental Co", isin=None, listing_date=None)]


def _bar(symbol: str, d: date, price: float) -> RawBar:
    return RawBar(
        symbol=symbol,
        date=d,
        open=Decimal(str(price)),
        high=Decimal(str(price + 1)),
        low=Decimal(str(price - 1)),
        close=Decimal(str(price)),
        volume=1_000_000,
        turnover_value=Decimal(str(price)) * 1_000_000,
    )


def _strategy() -> Strategy:
    return Strategy(
        name="incremental_test_strategy",
        version=1,
        config_hash="incr-1",
        config=StrategyConfig(
            name="incremental_test_strategy",
            version=1,
            engines=(EngineConfig(id="trend_template", enabled=True, weight=Decimal("1")),),
        ),
    )


def _make_engine() -> StrategyEngine:
    from momentum25.domain.engines.trend_template import TrendTemplateEngine

    registry = EngineRegistry()
    registry.register(TrendTemplateEngine())
    return StrategyEngine(engines=registry, scoring=ScoringEngineImpl(), ranking=RankingEngineImpl())


@pytest.mark.asyncio
async def test_incremental_rerun_only_fetches_sessions_since_latest_bar(
    db_session: AsyncSession,
) -> None:
    security_repo = SqlSecurityRepository(db_session)
    ohlcv_repo = SqlOHLCVRepository(db_session)
    screening_run_repo = SqlScreeningRunRepository(db_session)
    strategy_repo = SqlStrategyRepository(db_session)
    indicator_pipeline = IndicatorPipelineImpl(db_session)
    strategy = _strategy()
    await strategy_repo.upsert(strategy)
    await db_session.commit()

    # Seed 300 already-persisted days directly (bypassing ExecuteScreening),
    # so "latest persisted" is well-defined without a first full fetch.
    from momentum25.domain.entities.market_data import OHLCVBar
    from momentum25.infrastructure.persistence.models import SecurityModel

    sec = SecurityModel(symbol="INCR", name="Incremental Co", is_active=True)
    db_session.add(sec)
    await db_session.flush()
    await db_session.refresh(sec)

    start_date = date(2024, 1, 1)
    calendar = get_nse_trading_calendar()
    persisted_sessions = calendar.sessions_between(start_date, start_date + timedelta(days=450))[
        :300
    ]
    seed_bars = [
        OHLCVBar(
            date=d,
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            volume=1_000_000,
            turnover_value=Decimal("100000000"),
        )
        for d in persisted_sessions
    ]
    await ohlcv_repo.upsert_bars(sec.id, seed_bars)
    await db_session.commit()

    latest_persisted = persisted_sessions[-1]
    first_new_sessions = calendar.sessions_between(
        latest_persisted + timedelta(days=1), latest_persisted + timedelta(days=10)
    )[:3]
    expected_sessions = calendar.sessions_between(latest_persisted + timedelta(days=1), date.today())

    provider = _RecordingProvider(
        {d: [_bar("INCR", d, 100.0)] for d in first_new_sessions}
    )

    use_case = ExecuteScreening(
        market_data_provider=provider,
        security_repo=security_repo,
        ohlcv_repo=ohlcv_repo,
        screening_run_repo=screening_run_repo,
        indicator_pipeline=indicator_pipeline,
        strategy_engine=_make_engine(),
    )

    await use_case.execute(strategy_name=strategy.name, force=False)

    # Every fetched date must be a real trading session strictly after the
    # latest persisted bar -- no weekend/holiday date requested, nothing
    # from before the incremental start, and (the actual regression guard)
    # exactly the sessions in range -- not every calendar day.
    assert provider.fetch_calls
    assert all(d > latest_persisted for d in provider.fetch_calls)
    assert all(calendar.is_session(d) for d in provider.fetch_calls)
    assert provider.fetch_calls == expected_sessions


@pytest.mark.asyncio
async def test_background_execution_reaches_completed(db_session: AsyncSession) -> None:
    from momentum25.domain.entities.market_data import OHLCVBar
    from momentum25.infrastructure.persistence.models import SecurityModel

    security_repo = SqlSecurityRepository(db_session)
    ohlcv_repo = SqlOHLCVRepository(db_session)
    screening_run_repo = SqlScreeningRunRepository(db_session)
    strategy_repo = SqlStrategyRepository(db_session)
    strategy = _strategy()
    object.__setattr__(strategy, "name", "bg_test_strategy")
    object.__setattr__(strategy, "config", StrategyConfig(
        name="bg_test_strategy",
        version=1,
        engines=(EngineConfig(id="trend_template", enabled=True, weight=Decimal("1")),),
    ))
    strategy_id = await strategy_repo.upsert(strategy)
    object.__setattr__(strategy, "id", strategy_id)
    await db_session.commit()

    sec = SecurityModel(symbol="BGRUN", name="Background Run Co", is_active=True)
    db_session.add(sec)
    await db_session.flush()
    await db_session.refresh(sec)

    start_date = date(2024, 1, 1)
    bars = [
        OHLCVBar(
            date=start_date + timedelta(days=i),
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            volume=1_000_000,
            turnover_value=Decimal("100000000"),
        )
        for i in range(300)
    ]
    await ohlcv_repo.upsert_bars(sec.id, bars)
    await db_session.commit()

    from momentum25.domain.entities.run import ScreeningRun
    from momentum25.domain.value_objects.types import RunTrigger

    pending = ScreeningRun(
        strategy_id=strategy.id,
        run_date=date.today(),
        data_version="none",
        config_hash=strategy.config_hash,
        trigger=RunTrigger.MANUAL,
        status=RunStatus.PENDING,
    )
    run_id = await screening_run_repo.create(pending)
    await db_session.commit()

    # Bars already persisted through 2024-10-26; an incremental run with no
    # new sessions to fetch must still complete using the persisted universe
    # (rather than erroring "no market data available") -- see
    # ExecuteScreening.execute's incremental-with-nothing-new branch.
    empty_provider = _RecordingProvider({})
    completed_id = await run_screening_pipeline(
        "bg_test_strategy", run_id=run_id, market_data_provider=empty_provider
    )
    assert completed_id == run_id

    run = await screening_run_repo.get(run_id)
    assert run is not None
    assert run.status == RunStatus.COMPLETED
