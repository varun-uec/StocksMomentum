"""Integration test for HistoricalValidationUseCase's walk-forward fix (Objective 6).

Previously ``_execute_window`` only queried pre-existing completed runs and
never executed anything -- a window with zero prior runs silently reported
zero runs as if that were a real (rather than never-attempted) result. This
test proves the fix: given only raw OHLCV history and no prior runs, calling
``execute()`` must actually create new completed screening runs.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.application.use_cases.validation import HistoricalValidationUseCase
from momentum25.domain.entities.market_data import OHLCVBar
from momentum25.domain.entities.strategy import EngineConfig, Strategy, StrategyConfig
from momentum25.domain.scoring.ranking_engine import RankingEngineImpl
from momentum25.domain.scoring.scoring_engine import ScoringEngineImpl
from momentum25.domain.strategy.engine_registry import EngineRegistry
from momentum25.domain.strategy.strategy_engine import StrategyEngine
from momentum25.infrastructure.persistence.models import ScreeningRunModel, SecurityModel
from momentum25.infrastructure.persistence.repositories import (
    SqlOHLCVRepository,
    SqlScreeningRunRepository,
    SqlSecurityRepository,
    SqlStrategyRepository,
)
from momentum25.infrastructure.pipelines.indicator_pipeline import IndicatorPipelineImpl


def _uptrend_bars(days: int, start: date, base_price: float = 100.0) -> list[OHLCVBar]:
    bars = []
    price = base_price
    for i in range(days):
        bars.append(
            OHLCVBar(
                date=start + timedelta(days=i),
                open=Decimal(str(price)),
                high=Decimal(str(price + 2)),
                low=Decimal(str(price - 1)),
                close=Decimal(str(price + 1)),
                volume=1_000_000,
            )
        )
        price += 0.5
    return bars


@pytest.mark.asyncio
async def test_execute_window_creates_real_runs_not_just_reports_zero(
    db_session: AsyncSession,
) -> None:
    """A window with no prior runs must end up with newly-executed completed runs."""
    start_date = date(2024, 1, 1)

    security = SecurityModel(symbol="WALKFWD", name="Walk Forward Co", is_active=True)
    db_session.add(security)
    await db_session.flush()
    await db_session.refresh(security)

    ohlcv_repo = SqlOHLCVRepository(db_session)
    await ohlcv_repo.upsert_bars(security.id, _uptrend_bars(300, start_date, 100.0))
    await db_session.commit()

    strategy_repo = SqlStrategyRepository(db_session)
    from momentum25.domain.engines.trend_template import TrendTemplateEngine

    registry = EngineRegistry()
    registry.register(TrendTemplateEngine())
    strategy_engine = StrategyEngine(
        engines=registry, scoring=ScoringEngineImpl(), ranking=RankingEngineImpl()
    )
    strategy = Strategy(
        name="walkfwd_strategy",
        version=1,
        config_hash="abc",
        config=StrategyConfig(
            name="walkfwd_strategy",
            version=1,
            engines=(EngineConfig(id="trend_template", enabled=True, weight=Decimal("1")),),
        ),
    )
    await strategy_repo.upsert(strategy)
    await db_session.commit()

    use_case = HistoricalValidationUseCase(
        screening_run_repo=SqlScreeningRunRepository(db_session),
        strategy_repo=strategy_repo,
        ohlcv_repo=ohlcv_repo,
        security_repo=SqlSecurityRepository(db_session),
        indicator_pipeline=IndicatorPipelineImpl(db_session),
        strategy_engine=strategy_engine,
    )

    # No completed runs exist yet -- confirm the baseline.
    count_before = await db_session.scalar(select(func.count()).select_from(ScreeningRunModel))
    assert count_before == 0

    report = await use_case.execute("walkfwd_strategy", window_years=1, execute_missing=True)

    count_after = await db_session.scalar(select(func.count()).select_from(ScreeningRunModel))
    assert count_after > 0, "walk-forward execution must create real screening runs"

    window_result = next(r for r in report.windows if r.window.label == "1Y")
    assert window_result.total_runs > 0
    assert window_result.summary["newly_executed"] > 0

    # A 1Y window is far below the ~5-year regime-diversity floor -- the
    # multiple-comparison-bias warning must fire, not be silently omitted.
    assert "regime_diversity_warning" in window_result.summary


@pytest.mark.asyncio
async def test_execute_window_default_never_executes_new_runs(
    db_session: AsyncSession,
) -> None:
    """The default (interactive/API) call must never trigger new screening runs.

    Regression test: ``_execute_window``'s real-execution behavior, once
    unconditional, made the dashboard/API endpoints synchronously run a full
    screening pass for every missing weekly-sampled date in the window --
    multi-minute timeouts once the production dataset outgrew a monthly run
    cadence. The default must stay read-only: report on existing runs only
    and surface how many sampled dates have no run yet, rather than execute.
    """
    start_date = date(2024, 1, 1)

    security = SecurityModel(symbol="WALKFWD2", name="Walk Forward Co 2", is_active=True)
    db_session.add(security)
    await db_session.flush()
    await db_session.refresh(security)

    ohlcv_repo = SqlOHLCVRepository(db_session)
    await ohlcv_repo.upsert_bars(security.id, _uptrend_bars(300, start_date, 100.0))
    await db_session.commit()

    strategy_repo = SqlStrategyRepository(db_session)
    from momentum25.domain.engines.trend_template import TrendTemplateEngine

    registry = EngineRegistry()
    registry.register(TrendTemplateEngine())
    strategy_engine = StrategyEngine(
        engines=registry, scoring=ScoringEngineImpl(), ranking=RankingEngineImpl()
    )
    strategy = Strategy(
        name="walkfwd_strategy_readonly",
        version=1,
        config_hash="abc",
        config=StrategyConfig(
            name="walkfwd_strategy_readonly",
            version=1,
            engines=(EngineConfig(id="trend_template", enabled=True, weight=Decimal("1")),),
        ),
    )
    await strategy_repo.upsert(strategy)
    await db_session.commit()

    use_case = HistoricalValidationUseCase(
        screening_run_repo=SqlScreeningRunRepository(db_session),
        strategy_repo=strategy_repo,
        ohlcv_repo=ohlcv_repo,
        security_repo=SqlSecurityRepository(db_session),
        indicator_pipeline=IndicatorPipelineImpl(db_session),
        strategy_engine=strategy_engine,
    )

    count_before = await db_session.scalar(select(func.count()).select_from(ScreeningRunModel))
    assert count_before == 0

    report = await use_case.execute("walkfwd_strategy_readonly", window_years=1)

    count_after = await db_session.scalar(select(func.count()).select_from(ScreeningRunModel))
    assert count_after == count_before, "default call must not create new screening runs"

    window_result = next(r for r in report.windows if r.window.label == "1Y")
    assert window_result.summary["newly_executed"] == 0
    assert window_result.total_runs == 0
    assert window_result.summary["missing"] > 0
