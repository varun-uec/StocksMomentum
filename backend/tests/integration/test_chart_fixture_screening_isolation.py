"""Chart-only E2E candles must not enter equity analytics or screening."""

from __future__ import annotations

import importlib.util
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.application.services.rs_ratings import resolve_universe_rs_ratings
from momentum25.application.use_cases.market_context import GetMarketContext
from momentum25.application.use_cases.screening_orchestrator import ScreeningOrchestrator
from momentum25.domain.entities.market_data import OHLCVBar
from momentum25.domain.entities.strategy import EngineConfig, Strategy, StrategyConfig
from momentum25.domain.scoring.ranking_engine import RankingEngineImpl
from momentum25.domain.scoring.scoring_engine import ScoringEngineImpl
from momentum25.domain.strategy.engine_registry import EngineRegistry
from momentum25.domain.strategy.strategy_engine import StrategyEngine
from momentum25.domain.value_objects.instrument import is_equity
from momentum25.infrastructure.persistence.models import (
    BenchmarkIndexDailyModel,
    OHLCVDailyModel,
    ScreeningRunModel,
    SecurityModel,
)
from momentum25.infrastructure.persistence.point_in_time import (
    PointInTimeSecurityRepository,
    PointInTimeSource,
    current_revision,
)
from momentum25.infrastructure.persistence.point_in_time_screening import (
    PointInTimeHistoricalScreening,
)
from momentum25.infrastructure.persistence.repositories import (
    SqlBenchmarkIndexRepository,
    SqlOHLCVRepository,
    SqlScreeningRunRepository,
    SqlSecurityRepository,
    SqlStrategyRepository,
)
from momentum25.infrastructure.persistence.repositories.data_manifests import (
    SqlDataManifestRepository,
)
from momentum25.infrastructure.pipelines.indicator_pipeline import IndicatorPipelineImpl

_AS_OF = date(2026, 8, 7)
_CHART_SYMBOL = "E2ECANDLE"


def _chart_fixture_module() -> ModuleType:
    """Load the E2E candle generator without invoking its command-line entry point."""
    path = Path(__file__).resolve().parents[3] / "web" / "e2e" / "db.py"
    spec = importlib.util.spec_from_file_location("e2e_db_fixtures", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _strategy() -> Strategy:
    return Strategy(
        name="fixture-isolation",
        version=1,
        config_hash="fixture-isolation-v1",
        config=StrategyConfig(
            name="fixture-isolation",
            version=1,
            engines=(
                EngineConfig(id="trend_template", enabled=True, weight=Decimal("1")),
            ),
            indicators={"rs_return_weights": {"63": 1.0}},
        ),
    )


def _strategy_engine() -> StrategyEngine:
    from momentum25.domain.engines.trend_template import TrendTemplateEngine

    registry = EngineRegistry()
    registry.register(TrendTemplateEngine())
    return StrategyEngine(
        engines=registry,
        scoring=ScoringEngineImpl(),
        ranking=RankingEngineImpl(),
    )


async def _seed_equity_series(
    session: AsyncSession, symbol: str, dates: list[date], daily_growth: Decimal
) -> int:
    security = SecurityModel(
        symbol=symbol,
        name=f"Synthetic {symbol}",
        isin=f"INE{len(symbol):02d}000001",
        is_active=True,
    )
    session.add(security)
    await session.flush()
    bars: list[OHLCVBar] = []
    for index, bar_date in enumerate(dates):
        close = Decimal("100") + daily_growth * index
        open_price = close - Decimal("0.20")
        bars.append(
            OHLCVBar(
                date=bar_date,
                open=open_price,
                high=close + Decimal("0.50"),
                low=open_price - Decimal("0.50"),
                close=close,
                volume=1_000_000,
                turnover_value=close * 1_000_000,
            )
        )
    await SqlOHLCVRepository(session).upsert_bars(security.id, bars)
    return security.id


async def _breadth_and_rs(
    session: AsyncSession, strategy: Strategy
) -> tuple[object, dict[str, int]]:
    security_repo = SqlSecurityRepository(session)
    ohlcv_repo = SqlOHLCVRepository(session)
    context = await GetMarketContext(
        security_repo,
        ohlcv_repo,
        SqlBenchmarkIndexRepository(session),
        "NIFTY500",
    ).execute(_AS_OF)
    ratings = await resolve_universe_rs_ratings(
        security_repo,
        ohlcv_repo,
        strategy,
        _AS_OF,
        cache=None,
    )
    return context.breadth, ratings


async def _live_screening_run(
    session: AsyncSession, strategy: Strategy
) -> tuple[tuple[int, int, int, int], tuple[tuple[int, Decimal, Decimal, int | None], ...]]:
    security_repo = SqlSecurityRepository(session)
    ohlcv_repo = SqlOHLCVRepository(session)
    manifest = await SqlDataManifestRepository(session).capture()
    await session.commit()
    summary = await ScreeningOrchestrator(
        security_repo=security_repo,
        ohlcv_repo=ohlcv_repo,
        screening_run_repo=SqlScreeningRunRepository(session),
        indicator_pipeline=IndicatorPipelineImpl(session),
        strategy_engine=_strategy_engine(),
        strategy=strategy,
        strategy_repo=SqlStrategyRepository(session),
    ).run_daily_screening(_AS_OF, data_manifest=manifest)
    run = await session.scalar(
        select(ScreeningRunModel).where(ScreeningRunModel.data_version == manifest.data_version)
    )
    assert run is not None and run.id is not None
    counts = (
        summary.total_evaluated,
        summary.total_passed,
        summary.total_skipped_insufficient_data,
        summary.total_failed,
    )
    return counts, await _stored_ranking_snapshot(session, run.id)


async def _stored_ranking_snapshot(
    session: AsyncSession, run_id: int
) -> tuple[tuple[int, Decimal, Decimal, int | None], ...]:
    rankings, _ = await SqlScreeningRunRepository(session).get_rankings(
        run_id, limit=10_000, offset=0
    )
    return tuple(
        (row.security_id, row.momentum_score, row.buy_setup_score, row.rank)
        for row in rankings
    )


async def _point_in_time_run(
    session: AsyncSession, strategy: Strategy, suffix: str
) -> tuple[dict[str, object], tuple[tuple[int, Decimal, Decimal, int | None], ...]]:
    screening = PointInTimeHistoricalScreening(
        session=session,
        screening_run_repo=SqlScreeningRunRepository(session),
        strategy_repo=SqlStrategyRepository(session),
        strategy_engine=_strategy_engine(),
    )
    summary = await screening.execute(
        strategy_name=strategy.name,
        as_of_date=_AS_OF,
        run_suffix=suffix,
    )
    run_id = int(summary["run_id"])
    return summary, await _stored_ranking_snapshot(session, run_id)


@pytest.mark.asyncio
async def test_chart_only_candles_leave_equity_analytics_and_pit_screen_unchanged(
    db_session: AsyncSession,
) -> None:
    """The synthetic chart series cannot change live analytics or PIT equity ranks."""
    fixture = _chart_fixture_module()
    chart_bars = fixture.chart_fixture_bars()
    dates = [row[0] for row in chart_bars]
    assert dates[-1] == _AS_OF

    await _seed_equity_series(db_session, "EQUITYA", dates, Decimal("0.50"))
    await _seed_equity_series(db_session, "EQUITYB", dates, Decimal("0.75"))
    await _seed_equity_series(db_session, "EQUITYC", dates, Decimal("1.00"))
    session_closes = [Decimal(10_000 + index) for index in range(len(dates))]
    db_session.add_all(
        [
            BenchmarkIndexDailyModel(index_code="NIFTY500", date=day, close=close)
            for day, close in zip(dates, session_closes, strict=True)
        ]
    )
    strategy = _strategy()
    strategy_id = await SqlStrategyRepository(db_session).upsert(strategy)
    object.__setattr__(strategy, "id", strategy_id)
    await db_session.commit()

    baseline_breadth, baseline_rs = await _breadth_and_rs(db_session, strategy)
    baseline_live_screening, baseline_live_rankings = await _live_screening_run(
        db_session, strategy
    )
    baseline_summary, baseline_rankings = await _point_in_time_run(
        db_session, strategy, ":without-chart-fixture"
    )

    chart_security = SecurityModel(
        symbol=_CHART_SYMBOL,
        name="Synthetic E2E chart fixture",
        exchange="NSE",
        isin="INFE2ECANDL1",
        is_active=False,
    )
    db_session.add(chart_security)
    await db_session.flush()
    db_session.add_all(
        [
            OHLCVDailyModel(
                security_id=chart_security.id,
                date=bar_date,
                open=open_price,
                high=high,
                low=low,
                close=close,
                volume=volume,
                turnover_value=turnover,
                adj_factor=adjustment_factor,
                adj_close=close * adjustment_factor,
            )
            for (
                _security_id,
                bar_date,
                open_price,
                high,
                low,
                close,
                volume,
                turnover,
                adjustment_factor,
            ) in fixture.chart_fixture_rows(chart_security.id)
        ]
    )
    await db_session.commit()

    source = PointInTimeSource(db_session, _AS_OF, await current_revision(db_session))
    pit_universe = await PointInTimeSecurityRepository(source).list_active()
    pit_chart_security = next(s for s in pit_universe if str(s.symbol) == _CHART_SYMBOL)
    assert pit_chart_security.is_active is True  # PIT membership is based on listing dates.
    assert pit_chart_security.isin == "INFE2ECANDL1"
    assert is_equity(pit_chart_security.isin) is False

    fixture_breadth, fixture_rs = await _breadth_and_rs(db_session, strategy)
    fixture_live_screening, fixture_live_rankings = await _live_screening_run(
        db_session, strategy
    )
    fixture_summary, fixture_rankings = await _point_in_time_run(
        db_session, strategy, ":with-chart-fixture"
    )

    assert fixture_breadth == baseline_breadth
    assert fixture_rs == baseline_rs
    assert fixture_live_screening == baseline_live_screening
    assert fixture_live_screening[0] == 3
    assert fixture_live_rankings == baseline_live_rankings
    assert fixture_summary["total_evaluated"] == baseline_summary["total_evaluated"] == 3
    assert fixture_summary["total_passed"] == baseline_summary["total_passed"]
    assert fixture_rankings == baseline_rankings
    assert all(
        security_id != chart_security.id
        for security_id, _momentum, _setup, _rank in fixture_rankings
    )

    stored_fixture = await db_session.scalar(
        select(SecurityModel).where(SecurityModel.symbol == _CHART_SYMBOL)
    )
    assert stored_fixture is not None and stored_fixture.is_active is False
