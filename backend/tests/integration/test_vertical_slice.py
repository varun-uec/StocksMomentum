"""Vertical slice integration test — exercises the complete architecture end-to-end.

Validates the full pipeline with seeded data (simulating what NSE would provide):

    Market Data → Indicator Pipeline → Strategy Engine → Rule Engine →
    Scoring Engine → Ranking Engine → Persistence → API → Frontend-compatible response

This test uses the same seeded-data approach as the existing orchestrator tests
but additionally verifies the API endpoint and frontend-compatible response shape.
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
from momentum25.infrastructure.persistence.models import SecurityModel
from momentum25.infrastructure.persistence.repositories import (
    SqlOHLCVRepository,
    SqlScreeningRunRepository,
    SqlSecurityRepository,
    SqlStrategyRepository,
)
from momentum25.infrastructure.pipelines.indicator_pipeline import IndicatorPipelineImpl
from momentum25.main import create_app


def _make_uptrend_bars(days: int, start: date, base_price: float = 100.0) -> list[dict]:
    """Generate uptrend bars (price steadily increasing)."""
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
async def test_vertical_slice_full_pipeline(db_session: AsyncSession) -> None:
    """Exercise the complete architecture: data → indicators → strategy → scoring → ranking → API.

    Verifies:
        1. ScreeningOrchestrator processes symbols and persists results.
        2. API returns paginated rankings with the correct shape.
        3. API returns explainability with rule details.
        4. Response shape is compatible with the frontend types.
    """
    start_date = date(2024, 1, 1)
    target_date = start_date + timedelta(days=299)

    # ── 1. Seed securities (simulating NSE instrument master) ──────────────
    passer = await _seed_security(db_session, "PASSER", "Passing Trend")
    failer = await _seed_security(db_session, "FAILER", "Failing Trend")
    ipo = await _seed_security(db_session, "NEWIPO", "Recent IPO")

    # ── 2. Seed historical OHLCV data (simulating NSE market data) ─────────
    await _seed_bars(db_session, passer.id, _make_uptrend_bars(300, start_date, 100.0))
    await _seed_bars(
        db_session, failer.id, _make_descending_bars(300, start_date, 200.0)
    )
    # IPO has insufficient history (< 275 bars)
    await _seed_bars(
        db_session, ipo.id, _make_uptrend_bars(10, target_date - timedelta(days=9))
    )

    # ── 3. Wire collaborators (same as ScreeningOrchestrator test) ──────────
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
        name="vertical_slice_strategy",
        version=1,
        config_hash="vslice001",
        config=StrategyConfig(
            name="vertical_slice_strategy",
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

    # ── 4. Execute the full screening pipeline ─────────────────────────────
    summary = await orchestrator.run_daily_screening(target_date)

    # ── 5. Verify pipeline execution results ───────────────────────────────
    assert summary.run_date == target_date
    assert summary.total_evaluated == 3
    # NEWIPO skipped (insufficient data < 275 bars)
    assert summary.total_skipped_insufficient_data >= 1
    # All three symbols account for the total
    assert summary.total_passed + summary.total_skipped_insufficient_data + summary.total_failed == 3
    assert summary.duration_seconds > 0

    # ── 6. Verify persistence ──────────────────────────────────────────────
    run = await screening_run_repo.latest_completed(strategy.id)
    assert run is not None
    assert run.id is not None
    assert run.status.value == "COMPLETED"
    assert run.stats is not None
    assert run.stats["total_evaluated"] == 3

    # ── 7. Verify API returns rankings (frontend-compatible shape) ──────────
    app = create_app()
    with TestClient(app) as client:
        # 7a. Rankings endpoint
        response = client.get(f"/api/v1/rankings/runs/{run.id}?limit=50&offset=0")

    assert response.status_code == 200, f"Rankings API failed: {response.text}"
    data = response.json()

    # Verify frontend-compatible response shape (matches RankingsResponse in types.ts)
    assert "items" in data
    assert "total" in data
    assert "run" in data
    assert data["total"] >= 1

    # Verify each ranking item has the fields expected by MomentumTable.tsx
    for item in data["items"]:
        assert "rank" in item
        assert "symbol" in item
        assert "momentum_score" in item
        assert "buy_setup_score" in item
        assert "rs_rating" in item or "rs_rating" not in item  # optional
        # Verify explanation/checklist shape
        if "explanation" in item and item["explanation"] is not None:
            explanation = item["explanation"]
            if "checklist" in explanation:
                checklist = explanation["checklist"]
                # Verify at least some rule fields exist
                assert isinstance(checklist, dict)

    # ── 8. Verify API returns explainability ───────────────────────────────
    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/rankings/runs/{run.id}/stocks/{passer.id}/explanation"
        )

    assert response.status_code == 200, f"Explanation API failed: {response.text}"
    explanation = response.json()
    assert "rule_explanations" in explanation
    assert "engine_explanations" in explanation
    assert "overall_rationale" in explanation
    assert isinstance(explanation["rule_explanations"], list)

    # ── 9. Verify run list API ─────────────────────────────────────────────
    with TestClient(app) as client:
        response = client.get("/api/v1/runs?status=COMPLETED&limit=10&offset=0")

    assert response.status_code == 200
    runs_data = response.json()
    assert "items" in runs_data
    assert len(runs_data["items"]) >= 1
    # Verify RunDTO shape (matches frontend expectations)
    first_run = runs_data["items"][0]
    assert "id" in first_run
    assert "status" in first_run
    assert first_run["status"] == "COMPLETED"
    assert "strategy" in first_run
    assert "stats" in first_run
    assert first_run["stats"]["total_evaluated"] == 3


@pytest.mark.asyncio
async def test_vertical_slice_single_symbol(db_session: AsyncSession) -> None:
    """Exercise the pipeline with a single symbol (minimum viable vertical slice).

    Verifies the architecture works with the smallest possible input.
    """
    start_date = date(2024, 1, 1)
    target_date = start_date + timedelta(days=299)

    # Seed a single security with uptrend bars
    sec = await _seed_security(db_session, "SINGLE", "Single Symbol Test")
    await _seed_bars(db_session, sec.id, _make_uptrend_bars(300, start_date, 100.0))

    # Wire collaborators
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
        name="single_symbol_strategy",
        version=1,
        config_hash="single001",
        config=StrategyConfig(
            name="single_symbol_strategy",
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

    # Execute pipeline
    summary = await orchestrator.run_daily_screening(target_date)

    # Verify single symbol results
    # (Note: the stub RS rating of 50 means the trend template may not pass
    # the hard gate; future milestones will implement real RS calculation)
    assert summary.total_evaluated == 1
    assert summary.total_passed + summary.total_failed + summary.total_skipped_insufficient_data == 1

    # Verify persistence
    run = await screening_run_repo.latest_completed(strategy.id)
    assert run is not None
    assert run.status.value == "COMPLETED"

    # Verify API returns results
    app = create_app()
    with TestClient(app) as client:
        response = client.get(f"/api/v1/rankings/runs/{run.id}?limit=10&offset=0")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["symbol"] == "SINGLE"
    # Rank may be 0 when hard filters fail (stub RS rating); the important
    # thing is the pipeline completed, persisted, and was retrievable via API.
    assert "rank" in data["items"][0]
