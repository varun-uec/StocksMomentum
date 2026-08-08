"""Integration tests for the Screening & Explainability API.

Validates end-to-end API behavior: ranking retrieval, explainability payloads,
historical reconstruction, and pagination. Uses async TestClient against a
live FastAPI app instance (no HTTP transport).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.application.use_cases.screening_orchestrator import ScreeningOrchestrator
from momentum25.domain.entities.strategy import EngineConfig, Strategy, StrategyConfig
from momentum25.domain.scoring.ranking_engine import RankingEngineImpl
from momentum25.domain.scoring.scoring_engine import ScoringEngineImpl
from momentum25.domain.strategy.engine_registry import EngineRegistry
from momentum25.domain.strategy.strategy_engine import StrategyEngine
from momentum25.infrastructure.adapters import BhavcopyProvider
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


def _make_descending_bars(days: int, start: date, base_price: float = 200.0) -> list[dict]:
    """Generate bars with a steadily declining close (descending 200 SMA)."""
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
    market_data_provider = BhavcopyProvider(httpx.AsyncClient())
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
        market_data_provider=market_data_provider,
        indicator_pipeline=indicator_pipeline,
        strategy_engine=strategy_engine,
        strategy=strategy,
        strategy_repo=strategy_repo,
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
    market_data_provider = BhavcopyProvider(httpx.AsyncClient())
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
        market_data_provider=market_data_provider,
        indicator_pipeline=indicator_pipeline,
        strategy_engine=strategy_engine,
        strategy=strategy,
        strategy_repo=strategy_repo,
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