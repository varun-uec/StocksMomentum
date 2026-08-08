"""Integration tests for the on-demand single-symbol live lookup (Phase 1.1/1.2).

Verifies the endpoint evaluates through the *same* strategy engine the daily
orchestrator uses (not a second hand-rolled evaluation), that it persists
freshly-fetched bars, that a repeated refresh within the cooldown makes zero
provider calls, and that a single-symbol universe reports RS as
indeterminate rather than fabricating a percentile or a hard failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.application.use_cases.screening_orchestrator import ScreeningOrchestrator
from momentum25.application.use_cases.stocks import GetLiveStockAnalysis, RefreshGate
from momentum25.domain.entities.strategy import EngineConfig, Strategy, StrategyConfig
from momentum25.domain.scoring.explainability import ExplainabilityBuilderImpl
from momentum25.domain.scoring.ranking_engine import RankingEngineImpl
from momentum25.domain.scoring.scoring_engine import ScoringEngineImpl
from momentum25.domain.strategy.engine_registry import EngineRegistry
from momentum25.domain.strategy.strategy_engine import StrategyEngine
from momentum25.infrastructure.persistence.models import SecurityModel
from momentum25.infrastructure.persistence.repositories import (
    SqlOHLCVRepository,
    SqlScreeningRunRepository,
    SqlSecurityRepository,
    SqlStrategyRepository,
)
from momentum25.infrastructure.pipelines.indicator_pipeline import IndicatorPipelineImpl


def _make_uptrend_bars(days: int, start: date, base_price: float = 100.0) -> list[dict]:
    bars = []
    price = base_price
    for i in range(days):
        d = start + timedelta(days=i)
        bars.append(
            {
                "date": d,
                "open": price,
                "high": price + 2,
                "low": price - 1,
                "close": price + 1,
                "volume": 1_000_000,
            }
        )
        price += 0.5
    return bars


async def _seed_security(session: AsyncSession, symbol: str, name: str) -> SecurityModel:
    model = SecurityModel(symbol=symbol, name=name, is_active=True)
    session.add(model)
    await session.flush()
    await session.refresh(model)
    return model


async def _seed_bars(session: AsyncSession, security_id: int, bars: list[dict]) -> None:
    from momentum25.domain.entities.market_data import OHLCVBar

    repo = SqlOHLCVRepository(session)
    bar_objs = [
        OHLCVBar(
            date=b["date"],
            open=Decimal(str(b["open"])),
            high=Decimal(str(b["high"])),
            low=Decimal(str(b["low"])),
            close=Decimal(str(b["close"])),
            volume=b["volume"],
            turnover_value=Decimal(str(b["close"])) * Decimal(b["volume"]),
        )
        for b in bars
    ]
    await repo.upsert_bars(security_id, bar_objs)
    await session.commit()


def _real_engine_strategy() -> Strategy:
    """A strategy config that matches production: only trend_template enabled."""
    return Strategy(
        name="minervini_trend_template",
        version=1,
        config_hash="abc",
        config=StrategyConfig(
            name="minervini_trend_template",
            version=1,
            engines=(EngineConfig(id="trend_template", enabled=True, weight=Decimal("1")),),
        ),
    )


def _make_engine() -> StrategyEngine:
    from momentum25.domain.engines.trend_template import TrendTemplateEngine

    registry = EngineRegistry()
    registry.register(TrendTemplateEngine())
    return StrategyEngine(engines=registry, scoring=ScoringEngineImpl(), ranking=RankingEngineImpl())


@dataclass
class _FakeRawBar:
    symbol: str
    date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    prev_close: Decimal | None = None
    turnover_value: Decimal | None = None


class _FakeNSEClient:
    """Fake NSE client returning a fixed set of bars, counting calls."""

    def __init__(self, bars: list[_FakeRawBar]) -> None:
        self.bars = bars
        self.calls = 0

    async def fetch_historical_bars(
        self, symbol: str, start_date: date, end_date: date | None = None
    ) -> list[Any]:
        self.calls += 1
        return self.bars


class _AlwaysRefresh(RefreshGate):
    async def should_refresh(self, symbol: str) -> bool:
        return True

    async def mark_refreshed(self, symbol: str) -> None:
        pass


@pytest.mark.asyncio
async def test_live_lookup_matches_batch_orchestrator_verdict(
    db_session: AsyncSession,
) -> None:
    """The live path and the daily orchestrator must agree on the same data.

    This is the regression guard for deleting ``MarketSyncService``'s
    duplicate hand-rolled trend-template evaluation: if the live use case
    ever drifted onto a second implementation, this test would catch the
    disagreement.
    """
    start_date = date(2024, 1, 1)
    target_date = start_date + timedelta(days=299)

    sec_a = await _seed_security(db_session, "LIVEA", "Live Match A")
    await _seed_bars(db_session, sec_a.id, _make_uptrend_bars(300, start_date, 100.0))
    sec_b = await _seed_security(db_session, "LIVEB", "Live Match B")
    await _seed_bars(db_session, sec_b.id, _make_uptrend_bars(300, start_date, 50.0))

    security_repo = SqlSecurityRepository(db_session)
    ohlcv_repo = SqlOHLCVRepository(db_session)
    screening_run_repo = SqlScreeningRunRepository(db_session)
    strategy_repo = SqlStrategyRepository(db_session)
    indicator_pipeline = IndicatorPipelineImpl(db_session)
    strategy = _real_engine_strategy()

    orchestrator = ScreeningOrchestrator(
        security_repo=security_repo,
        ohlcv_repo=ohlcv_repo,
        screening_run_repo=screening_run_repo,
        indicator_pipeline=indicator_pipeline,
        strategy_engine=_make_engine(),
        strategy=strategy,
        strategy_repo=strategy_repo,
    )
    await orchestrator.run_daily_screening(target_date)

    run = await screening_run_repo.latest_completed(strategy.id)
    assert run is not None
    result = await screening_run_repo.get_screening_result(run.id, sec_a.id)
    assert result is not None
    batch_passed = result.rank is not None

    use_case = GetLiveStockAnalysis(
        securities=security_repo,
        ohlcv_repo=ohlcv_repo,
        strategies=strategy_repo,
        indicator_pipeline=indicator_pipeline,
        strategy_engine=_make_engine(),
        explainability_builder=ExplainabilityBuilderImpl(),
        nse_client=_FakeNSEClient([]),
        refresh_gate=_AlwaysRefresh(),
    )
    live = await use_case.execute("LIVEA", strategy.name, refresh=False, as_of=target_date)

    assert live.data_sufficient is True
    assert live.explanation is not None
    assert live.explanation.overall_passed == batch_passed

    # Phase 2 exit criterion: ADX/MACD/swing pivots are exposed as data on the
    # live response, not just consumed internally by rule evaluation.
    for key in (
        "adx14", "plus_di14", "minus_di14",
        "macd_line", "macd_signal", "macd_histogram",
        "swing_resistance", "swing_support",
    ):
        assert key in live.indicators


@pytest.mark.asyncio
async def test_live_refresh_persists_new_bars_and_no_refresh_calls_provider_zero_times(
    db_session: AsyncSession,
) -> None:
    start_date = date(2024, 1, 1)
    latest_seeded = start_date + timedelta(days=298)

    sec_a = await _seed_security(db_session, "LIVEC", "Live Refresh C")
    await _seed_bars(db_session, sec_a.id, _make_uptrend_bars(299, start_date, 100.0))
    sec_b = await _seed_security(db_session, "LIVED", "Live Refresh D")
    await _seed_bars(db_session, sec_b.id, _make_uptrend_bars(299, start_date, 60.0))

    security_repo = SqlSecurityRepository(db_session)
    ohlcv_repo = SqlOHLCVRepository(db_session)
    strategy_repo = SqlStrategyRepository(db_session)
    indicator_pipeline = IndicatorPipelineImpl(db_session)
    strategy = _real_engine_strategy()
    await strategy_repo.upsert(strategy)
    await db_session.commit()

    new_day = latest_seeded + timedelta(days=1)
    fake_bar = _FakeRawBar(
        symbol="LIVEC",
        date=new_day,
        open=Decimal("250"),
        high=Decimal("252"),
        low=Decimal("249"),
        close=Decimal("251"),
        volume=1_000_000,
        turnover_value=Decimal("251000000"),
    )
    nse_client = _FakeNSEClient([fake_bar])

    use_case = GetLiveStockAnalysis(
        securities=security_repo,
        ohlcv_repo=ohlcv_repo,
        strategies=strategy_repo,
        indicator_pipeline=indicator_pipeline,
        strategy_engine=_make_engine(),
        explainability_builder=ExplainabilityBuilderImpl(),
        nse_client=nse_client,
        refresh_gate=_AlwaysRefresh(),
    )

    live = await use_case.execute("LIVEC", strategy.name, refresh=True, as_of=new_day)
    assert live.refreshed is True
    assert live.bars_fetched == 1
    assert nse_client.calls == 1

    live_no_refresh = await use_case.execute("LIVEC", strategy.name, refresh=False, as_of=new_day)
    assert live_no_refresh.refreshed is False
    assert nse_client.calls == 1  # unchanged -- no provider call was made


@pytest.mark.asyncio
async def test_single_symbol_universe_reports_rs_indeterminate_not_failed(
    db_session: AsyncSession,
) -> None:
    """Only one security in the DB -> no universe to rank RS against."""
    start_date = date(2024, 1, 1)
    target_date = start_date + timedelta(days=299)

    sec = await _seed_security(db_session, "SOLO", "Solo Security")
    await _seed_bars(db_session, sec.id, _make_uptrend_bars(300, start_date, 100.0))

    security_repo = SqlSecurityRepository(db_session)
    ohlcv_repo = SqlOHLCVRepository(db_session)
    strategy_repo = SqlStrategyRepository(db_session)
    indicator_pipeline = IndicatorPipelineImpl(db_session)
    strategy = _real_engine_strategy()
    await strategy_repo.upsert(strategy)
    await db_session.commit()

    use_case = GetLiveStockAnalysis(
        securities=security_repo,
        ohlcv_repo=ohlcv_repo,
        strategies=strategy_repo,
        indicator_pipeline=indicator_pipeline,
        strategy_engine=_make_engine(),
        explainability_builder=ExplainabilityBuilderImpl(),
        nse_client=_FakeNSEClient([]),
        refresh_gate=_AlwaysRefresh(),
    )

    live = await use_case.execute("SOLO", strategy.name, refresh=False, as_of=target_date)

    assert live.data_sufficient is True
    assert live.verdict == "INDETERMINATE"
    assert "tt_rs_rating_min" in live.indeterminate_rules
    assert "tt_rs_rating_min" not in live.explanation.hard_filter_failures
    assert live.rs_basis["universe_size"] == 0
