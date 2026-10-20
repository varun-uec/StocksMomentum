"""Integration tests for the Screening & Explainability API.

Validates end-to-end API behavior: ranking retrieval, explainability payloads,
historical reconstruction, and pagination. Uses async TestClient against a
live FastAPI app instance (no HTTP transport).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.application.use_cases.screening_orchestrator import ScreeningOrchestrator
from momentum25.domain.entities.strategy import EngineConfig, Strategy, StrategyConfig
from momentum25.domain.scoring.ranking_engine import RankingEngineImpl
from momentum25.domain.scoring.scoring_engine import ScoringEngineImpl
from momentum25.domain.strategy.engine_registry import EngineRegistry
from momentum25.domain.strategy.strategy_engine import StrategyEngine
from momentum25.infrastructure.calendar.nse_calendar import get_nse_trading_calendar
from momentum25.infrastructure.persistence.models import (
    SecurityModel,
)
from momentum25.infrastructure.persistence.repositories import (
    SqlOHLCVRepository,
    SqlScreeningRunRepository,
    SqlSecurityRepository,
    SqlStrategyRepository,
)
from momentum25.infrastructure.pipelines.indicator_pipeline import IndicatorPipelineImpl
from momentum25.main import create_app


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
async def test_rankings_api_returns_paginated_results(db_session: AsyncSession) -> None:
    """GET /api/v1/rankings/runs/{run_id} returns paginated rankings."""
    start_date = date(2024, 1, 1)
    target_date = start_date + timedelta(days=299)

    # Seed security and bars
    sec = await _seed_security(db_session, "PASSER", "Passing Trend")
    await _seed_bars(db_session, sec.id, _make_uptrend_bars(300, start_date, 100.0))

    # Execute screening and persist results
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
        calendar=get_nse_trading_calendar(),
    )

    await orchestrator.run_daily_screening(target_date)

    # Fetch run id
    run = await screening_run_repo.latest_completed(strategy.id)
    assert run is not None

    # Call API via TestClient
    app = create_app()
    with TestClient(app) as client:
        response = client.get(f"/api/v1/rankings/runs/{run.id}?limit=1&offset=0")

    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert len(data["items"]) <= 1
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_explanation_api_returns_rule_details(db_session: AsyncSession) -> None:
    """GET rankings/runs/{run_id}/stocks/{security_id}/explanation returns full explainability."""
    start_date = date(2024, 1, 1)
    target_date = start_date + timedelta(days=299)

    sec = await _seed_security(db_session, "PASSER2", "Passing Trend 2")
    await _seed_bars(db_session, sec.id, _make_uptrend_bars(300, start_date, 100.0))

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
        name="test_strategy2",
        version=1,
        config_hash="def",
        config=StrategyConfig(
            name="test_strategy2",
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
        calendar=get_nse_trading_calendar(),
    )

    await orchestrator.run_daily_screening(target_date)
    run = await screening_run_repo.latest_completed(strategy.id)
    assert run is not None

    app = create_app()
    with TestClient(app) as client:
        response = client.get(f"/api/v1/rankings/runs/{run.id}/stocks/{sec.id}/explanation")

    assert response.status_code == 200
    data = response.json()
    assert "rule_explanations" in data
    assert "engine_explanations" in data
    assert "overall_rationale" in data
    assert isinstance(data["rule_explanations"], list)

@pytest.mark.asyncio
async def test_rankings_pages_never_overlap_on_tied_ranks(db_session: AsyncSession) -> None:
    """Unqualified rows all have rank NULL; paging must still visit each row once, in order."""
    from momentum25.infrastructure.persistence.models import (
        ScreeningResultModel,
        ScreeningRunModel,
        StrategyModel,
    )

    strategy = StrategyModel(name="tie_test", version=1, config={}, config_hash="h")
    db_session.add(strategy)
    await db_session.flush()
    run = ScreeningRunModel(
        strategy_id=strategy.id,
        run_date=date(2026, 1, 2),
        data_version="v",
        config_hash="h",
        status="COMPLETED",
        trigger="MANUAL",
    )
    db_session.add(run)
    securities = [await _seed_security(db_session, f"TIE{i}", f"Tie {i}") for i in range(7)]
    for i, sec in enumerate(reversed(securities)):
        db_session.add(
            ScreeningResultModel(
                run_id=run.id,
                security_id=sec.id,
                momentum_score=Decimal(10),
                buy_setup_score=Decimal(10),
                hard_filters_passed=i < 2,
                rank=i + 1 if i < 2 else None,
            )
        )
    await db_session.commit()

    repo = SqlScreeningRunRepository(db_session)
    paged = [r for offset in range(7) for r in (await repo.get_rankings(run.id, 1, offset))[0]]
    whole, total = await repo.get_rankings(run.id, 100, 0)
    assert total == 7
    assert [r.security_id for r in paged] == [r.security_id for r in whole]
    unranked = [r.security_id for r in whole if r.rank is None]
    assert unranked == sorted(unranked) and len(unranked) == 5


@pytest.mark.asyncio
async def test_latest_run_on_or_before_a_replay_date(db_session: AsyncSession) -> None:
    """Replay sees the newest live or historical run up to its date, never a research run."""
    from momentum25.infrastructure.persistence.models import ScreeningRunModel, StrategyModel

    config = {
        "name": "replay_runs",
        "version": 1,
        "engines": [{"id": "trend_template", "enabled": True, "weight": "1"}],
    }
    strategy = StrategyModel(name="replay_runs", version=1, config=config, config_hash="h")
    db_session.add(strategy)
    await db_session.flush()
    runs = {
        "live_old": (date(2026, 1, 2), "v1"),
        "historical": (date(2026, 1, 5), "historical:v1"),
        "research": (date(2026, 1, 6), "v1:research:7"),
        "live_new": (date(2026, 1, 8), "v2"),
    }
    ids = {}
    for name, (run_date, version) in runs.items():
        model = ScreeningRunModel(
            strategy_id=strategy.id,
            run_date=run_date,
            data_version=version,
            config_hash="h",
            status="COMPLETED",
            trigger="MANUAL",
        )
        db_session.add(model)
        await db_session.flush()
        ids[name] = model.id
    await db_session.commit()

    def latest(on_or_before: str | None) -> int | None:
        query = f"&on_or_before={on_or_before}" if on_or_before else ""
        with TestClient(create_app()) as client:
            body = client.get(f"/api/v1/runs/latest?strategy=replay_runs{query}").json()
        return body["id"] if body else None

    assert latest(None) == ids["live_new"]
    assert latest("2026-01-07") == ids["historical"]
    assert latest("2026-01-05") == ids["historical"]
    assert latest("2026-01-04") == ids["live_old"]
    assert latest("2026-01-01") is None
