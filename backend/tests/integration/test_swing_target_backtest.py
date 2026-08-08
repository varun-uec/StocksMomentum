"""Integration test for the swing target/stop backtest use case (Phase 3.3).

Proves the use case's I/O wiring end-to-end: it finds a real passing signal
from a completed screening run, computes the same entry/ATR/target the
production indicator pipeline would, fetches the right forward bars, and
reports the correct trade outcome -- against a real Postgres-backed run, not
mocks. The trade-decision logic itself (target-vs-stop-first, R-multiples,
aggregation) is already covered by tests/unit/test_swing_targets.py; this
test is about whether the use case correctly assembles real signals and real
forward data for that logic to run against.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.application.use_cases.research.swing_target_backtest import (
    SwingTargetBacktestUseCase,
)
from momentum25.application.use_cases.screening_orchestrator import ScreeningOrchestrator
from momentum25.domain.entities.market_data import OHLCVBar
from momentum25.domain.entities.strategy import EngineConfig, Strategy, StrategyConfig
from momentum25.domain.research.swing_targets import compute_swing_target_plan
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


def _make_uptrend_bars(
    days: int, start: date, base_price: float = 100.0, step: float = 0.5
) -> list[OHLCVBar]:
    bars = []
    price = base_price
    for i in range(days):
        d = start + timedelta(days=i)
        bars.append(
            OHLCVBar(
                date=d,
                open=Decimal(str(price)),
                high=Decimal(str(price + 2)),
                low=Decimal(str(price - 1)),
                close=Decimal(str(price + 1)),
                volume=1_000_000,
                turnover_value=Decimal(str(price + 1)) * 1_000_000,
            )
        )
        price += step
    return bars


def _make_engine() -> StrategyEngine:
    from momentum25.domain.engines.trend_template import TrendTemplateEngine

    registry = EngineRegistry()
    registry.register(TrendTemplateEngine())
    return StrategyEngine(
        engines=registry, scoring=ScoringEngineImpl(), ranking=RankingEngineImpl()
    )


@pytest.mark.asyncio
async def test_backtest_finds_real_signal_and_reports_correct_outcome(
    db_session: AsyncSession,
) -> None:
    start_date = date(2024, 1, 1)
    run_date = start_date + timedelta(days=299)

    sec = SecurityModel(symbol="BTEST", name="Backtest Co", is_active=True)
    db_session.add(sec)
    weak_sec = SecurityModel(symbol="BWEAK", name="Weak RS Co", is_active=True)
    db_session.add(weak_sec)
    await db_session.flush()
    await db_session.refresh(sec)
    await db_session.refresh(weak_sec)

    ohlcv_repo = SqlOHLCVRepository(db_session)
    # A second, slower-moving security so RS-rating has a real universe to
    # percentile against (Phase 1.2: a lone security has no RS universe at
    # all, which would fail tt_rs_rating_min and never pass hard filters).
    await ohlcv_repo.upsert_bars(sec.id, _make_uptrend_bars(300, start_date, 100.0))
    await ohlcv_repo.upsert_bars(weak_sec.id, _make_uptrend_bars(300, start_date, 100.0, step=0.05))
    await db_session.commit()

    strategy = Strategy(
        name="backtest_strategy",
        version=1,
        config_hash="bt-1",
        config=StrategyConfig(
            name="backtest_strategy",
            version=1,
            engines=(EngineConfig(id="trend_template", enabled=True, weight=Decimal("1")),),
        ),
    )
    security_repo = SqlSecurityRepository(db_session)
    screening_run_repo = SqlScreeningRunRepository(db_session)
    strategy_repo = SqlStrategyRepository(db_session)
    indicator_pipeline = IndicatorPipelineImpl(db_session)

    orchestrator = ScreeningOrchestrator(
        security_repo=security_repo,
        ohlcv_repo=ohlcv_repo,
        screening_run_repo=screening_run_repo,
        indicator_pipeline=indicator_pipeline,
        strategy_engine=_make_engine(),
        strategy=strategy,
        strategy_repo=strategy_repo,
    )
    await orchestrator.run_daily_screening(run_date)

    run = await screening_run_repo.latest_completed(strategy.id)
    assert run is not None
    result = await screening_run_repo.get_screening_result(run.id, sec.id)
    assert result is not None and result.rank is not None, "fixture must actually pass hard filters"

    # Independently compute the same plan the use case's internals will
    # derive, so the test doesn't just mirror the implementation blindly --
    # it fixes an expected entry/stop/target and then engineers bars around it.
    indicators = await indicator_pipeline.compute("BTEST", run_date, strategy.config.indicators)
    assert indicators.atr14 is not None
    series = await ohlcv_repo.get_series(sec.id, lookback_days=1, as_of=run_date)
    entry = series.latest.close
    plan = compute_swing_target_plan(entry, indicators.atr14, indicators.swing_resistance)
    assert plan is not None

    # Engineer forward bars so the stop is unambiguously hit on day 2.
    forward_bars = [
        OHLCVBar(
            date=run_date + timedelta(days=1),
            open=entry, high=entry + 1, low=entry - 1, close=entry, volume=1_000_000,
        ),
        OHLCVBar(
            date=run_date + timedelta(days=2),
            open=plan.stop, high=plan.stop, low=plan.stop - Decimal("1"), close=plan.stop,
            volume=1_000_000,
        ),
    ]
    await ohlcv_repo.upsert_bars(sec.id, forward_bars)
    await db_session.commit()

    use_case = SwingTargetBacktestUseCase(
        screening_run_repo=screening_run_repo,
        security_repo=security_repo,
        ohlcv_repo=ohlcv_repo,
        strategy_repo=strategy_repo,
        indicator_pipeline=indicator_pipeline,
        max_holding_days=20,
    )
    report = await use_case.execute(
        "backtest_strategy", start_date=run_date, end_date=run_date
    )

    assert report.total_trades == 1
    assert report.stop_hits == 1
    assert report.target_hits == 0
    assert report.hit_rate == Decimal("0")
    assert report.avg_r_multiple == Decimal("-1")


@pytest.mark.asyncio
async def test_backtest_reports_zero_trades_when_no_runs_in_window(
    db_session: AsyncSession,
) -> None:
    """No completed runs for the strategy in the window -> an honest empty report, not an error."""
    screening_run_repo = SqlScreeningRunRepository(db_session)
    security_repo = SqlSecurityRepository(db_session)
    ohlcv_repo = SqlOHLCVRepository(db_session)
    strategy_repo = SqlStrategyRepository(db_session)
    indicator_pipeline = IndicatorPipelineImpl(db_session)

    use_case = SwingTargetBacktestUseCase(
        screening_run_repo=screening_run_repo,
        security_repo=security_repo,
        ohlcv_repo=ohlcv_repo,
        strategy_repo=strategy_repo,
        indicator_pipeline=indicator_pipeline,
    )
    report = await use_case.execute(
        "nonexistent_strategy_xyz", start_date=date(2020, 1, 1), end_date=date(2020, 12, 31)
    )
    assert report.total_trades == 0
    assert report.hit_rate is None
    assert report.avg_r_multiple is None
