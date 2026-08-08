"""Seed synthetic demo data for local end-to-end verification.

Generates 30 securities with 300 days of uptrend/downtrend/sideways OHLCV bars,
then runs the screening orchestrator for ``minervini_trend_template`` so the
dashboard has a completed run with rankings to display.

This is a verification/operations utility, not a product feature.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

# Add src to path so this script can be run standalone
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.application.use_cases.screening_orchestrator import ScreeningOrchestrator
from momentum25.domain.entities.market_data import OHLCVBar
from momentum25.domain.entities.strategy import EngineConfig, Strategy, StrategyConfig
from momentum25.domain.scoring.ranking_engine import RankingEngineImpl
from momentum25.domain.scoring.scoring_engine import ScoringEngineImpl
from momentum25.domain.strategy.bootstrap import register_builtin_engines
from momentum25.domain.strategy.engine_registry import EngineRegistry
from momentum25.domain.strategy.strategy_engine import StrategyEngine
from momentum25.infrastructure.adapters import BhavcopyProvider
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.models import SecurityModel
from momentum25.infrastructure.persistence.repositories import (
    SqlOHLCVRepository,
    SqlScreeningRunRepository,
    SqlSecurityRepository,
    SqlStrategyRepository,
)
from momentum25.infrastructure.pipelines.indicator_pipeline import IndicatorPipelineImpl


DEMO_SYMBOLS = [
    ("RELIANCE", "Reliance Industries"),
    ("TCS", "Tata Consultancy Services"),
    ("INFY", "Infosys"),
    ("HDFCBANK", "HDFC Bank"),
    ("ICICIBANK", "ICICI Bank"),
    ("HINDUNILVR", "Hindustan Unilever"),
    ("SBIN", "State Bank of India"),
    ("BHARTIARTL", "Bharti Airtel"),
    ("ITC", "ITC Limited"),
    ("KOTAKBANK", "Kotak Mahindra Bank"),
    ("LT", "Larsen & Toubro"),
    ("AXISBANK", "Axis Bank"),
    ("BAJFINANCE", "Bajaj Finance"),
    ("ASIANPAINT", "Asian Paints"),
    ("MARUTI", "Maruti Suzuki"),
    ("TITAN", "Titan Company"),
    ("SUNPHARMA", "Sun Pharmaceutical"),
    ("ULTRACEMCO", "UltraTech Cement"),
    ("NESTLEIND", "Nestle India"),
    ("WIPRO", "Wipro"),
    ("POWERGRID", "Power Grid Corporation"),
    ("NTPC", "NTPC Limited"),
    ("M&M", "Mahindra & Mahindra"),
    ("ADANIENT", "Adani Enterprises"),
    ("GRASIM", "Grasim Industries"),
    ("TATAMOTORS", "Tata Motors"),
    ("HCLTECH", "HCL Technologies"),
    ("TECHM", "Tech Mahindra"),
    ("JSWSTEEL", "JSW Steel"),
    ("ONGC", "Oil & Natural Gas Corporation"),
]


def _make_bars(
    days: int,
    start: date,
    base_price: float,
    trend: str = "up",
    volatility: float = 1.0,
) -> list[dict]:
    """Generate synthetic daily OHLCV bars.

    Produces smooth exponential trends so the Minervini trend-template gate
    can be satisfied by the strongest symbols.
    """
    bars = []
    price = base_price
    for i in range(days):
        d = start + timedelta(days=i)

        if trend == "up":
            # Steady exponential uptrend (~0.3% daily) with small noise
            daily_return = 0.003 + (i * 0.00005)
        elif trend == "down":
            # Steady downtrend
            daily_return = -0.003 - (i * 0.00005)
        else:
            # Sideways with small oscillation
            daily_return = (i % 10 - 4.5) * 0.0005

        noise = (i % 5 - 2) * volatility * 0.002 * price
        open_p = price * (1 + noise / price)
        close_p = price * (1 + daily_return + noise / price)
        high_p = max(open_p, close_p) * 1.005
        low_p = min(open_p, close_p) * 0.995

        bars.append(
            {
                "date": d,
                "open": round(open_p, 2),
                "high": round(high_p, 2),
                "low": round(low_p, 2),
                "close": round(close_p, 2),
                "volume": 1_000_000 + (i * 1000),
            }
        )
        price = close_p
    return bars


async def _seed_security(session: AsyncSession, symbol: str, name: str) -> SecurityModel:
    """Insert a security and return its ORM model."""
    model = SecurityModel(symbol=symbol, name=name, is_active=True)
    session.add(model)
    await session.flush()
    await session.refresh(model)
    return model


async def _seed_bars(
    session: AsyncSession,
    security_id: int,
    bars: list[dict],
) -> None:
    """Bulk upsert bars for a security."""
    repo = SqlOHLCVRepository(session)
    bar_objs = [
        OHLCVBar(
            date=b["date"],
            open=Decimal(str(b["open"])),
            high=Decimal(str(b["high"])),
            low=Decimal(str(b["low"])),
            close=Decimal(str(b["close"])),
            volume=b["volume"],
        )
        for b in bars
    ]
    await repo.upsert_bars(security_id, bar_objs)


async def main() -> None:
    """Seed demo data and run a screening for minervini_trend_template."""
    register_builtin_engines()
    database = get_database()
    async with database.session() as session:
        security_repo = SqlSecurityRepository(session)
        ohlcv_repo = SqlOHLCVRepository(session)
        screening_run_repo = SqlScreeningRunRepository(session)
        strategy_repo = SqlStrategyRepository(session)

        # Ensure minervini_trend_template strategy exists
        strategy = await strategy_repo.get_active("minervini_trend_template")
        if strategy is None:
            print("Strategy minervini_trend_template not found; aborting.")
            return

        start_date = date(2024, 1, 1)
        target_date = start_date + timedelta(days=299)

        # Seed 30 securities with mixed trends
        trends = ["up"] * 20 + ["down"] * 5 + ["flat"] * 5
        for idx, (symbol, name) in enumerate(DEMO_SYMBOLS):
            sec = await _seed_security(session, symbol, name)
            base_price = 100.0 + (idx * 10)
            bars = _make_bars(300, start_date, base_price, trend=trends[idx])
            await _seed_bars(session, sec.id, bars)
            print(f"Seeded {symbol}: {len(bars)} bars")

        await session.commit()

        # Run the screening orchestrator
        # Use the global engine registry populated by register_builtin_engines
        from momentum25.domain.strategy.engine_registry import engine_registry

        register_builtin_engines()
        scoring_engine = ScoringEngineImpl()
        ranking_engine = RankingEngineImpl()
        strategy_engine = StrategyEngine(
            engines=engine_registry,
            scoring=scoring_engine,
            ranking=ranking_engine,
        )
        indicator_pipeline = IndicatorPipelineImpl(session)
        market_data_provider = BhavcopyProvider(httpx.AsyncClient())

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

        summary = await orchestrator.run_daily_screening(target_date)
        print(
            f"Screening completed: evaluated={summary.total_evaluated}, "
            f"passed={summary.total_passed}, failed={summary.total_failed}, "
            f"skipped={summary.total_skipped_insufficient_data}"
        )

        run = await screening_run_repo.latest_completed(strategy.id)
        if run:
            print(f"Demo run id: {run.id}")


if __name__ == "__main__":
    asyncio.run(main())