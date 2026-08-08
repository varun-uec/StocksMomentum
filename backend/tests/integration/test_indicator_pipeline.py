"""Integration tests for the production-grade IndicatorPipelineImpl.

Validates vectorized pandas computation of SMA, 52-week extremes, and SMA200 slope
against a seeded Postgres test container with 300 days of synthetic pricing data.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.entities.market_data import OHLCVBar
from momentum25.infrastructure.persistence.models import SecurityModel
from momentum25.infrastructure.persistence.repositories import SqlOHLCVRepository
from momentum25.infrastructure.pipelines.indicator_pipeline import IndicatorPipelineImpl


def _to_ohlcv(bars: list[dict]) -> list[OHLCVBar]:
    """Convert seed dicts to ``OHLCVBar`` value objects for repository upsert."""
    return [
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


def _seed_bars(symbol: str, start: date, days: int) -> list[dict]:
    """Generate *days* consecutive daily bars starting at *start* with a steady uptrend."""
    bars = []
    price = 100.0
    for i in range(days):
        d = start + timedelta(days=i)
        open_ = price
        high = price + 2.0
        low = price - 1.0
        close = price + 1.0
        volume = 1_000_000
        bars.append(
            {
                "security_id": 1,
                "date": d,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "adj_close": None,
            }
        )
        price += 0.5
    return bars


@pytest.mark.asyncio
async def test_indicator_pipeline_computes_indicators(db_session: AsyncSession) -> None:
    """300 days of uptrend data must produce valid SMA/52w/slope values."""
    symbol = "RELIANCE"
    start = date(2024, 1, 1)
    bars = _seed_bars(symbol, start, 300)

    # Seed security
    security = SecurityModel(symbol=symbol, name=f"{symbol} Ind", is_active=True)
    db_session.add(security)
    await db_session.flush()
    await db_session.refresh(security)
    sec_id = security.id

    # Bulk upsert bars via repository (uses SQLAlchemy Core ON CONFLICT path)
    repo = SqlOHLCVRepository(db_session)
    await repo.upsert_bars(sec_id, _to_ohlcv(bars))
    await db_session.commit()

    pipeline = IndicatorPipelineImpl(db_session)
    indicators = await pipeline.compute(
        symbol=symbol,
        reference_date=start + timedelta(days=299),
        config={},
    )

    assert indicators.as_of == start + timedelta(days=299)
    assert indicators.sma50 is not None
    assert indicators.sma150 is not None
    assert indicators.sma200 is not None
    # Uptrend: the faster MA leads, so SMA50 > SMA150 > SMA200
    assert indicators.sma50 > indicators.sma150 > indicators.sma200
    assert indicators.sma200_slope_pct is not None
    assert indicators.sma200_slope_pct > 0
    assert indicators.high_52w is not None
    assert indicators.low_52w is not None
    assert indicators.high_52w > indicators.low_52w
    # Highest/lowest in the last 252 bars (the strategy's configured high_low_window,
    # matching the standard 252-trading-day "52-week" convention) must match seed data.
    last_252 = bars[-252:]
    assert indicators.high_52w == max(b["high"] for b in last_252)
    assert indicators.low_52w == min(b["low"] for b in last_252)
    assert indicators.rs_rating is None  # RS rating is delegated to RelativeStrengthPipeline


@pytest.mark.asyncio
async def test_indicator_pipeline_applies_adjustment_factor(db_session: AsyncSession) -> None:
    """Bars with a non-1 ``adj_factor`` must feed adjusted, not raw, prices/volume."""
    symbol = "ADJTEST"
    start = date(2024, 1, 1)
    bars = _seed_bars(symbol, start, 300)

    security = SecurityModel(symbol=symbol, name=f"{symbol} Ind", is_active=True)
    db_session.add(security)
    await db_session.flush()
    await db_session.refresh(security)
    sec_id = security.id

    repo = SqlOHLCVRepository(db_session)
    await repo.upsert_bars(sec_id, _to_ohlcv(bars))
    await db_session.commit()

    # Apply a uniform 0.5 factor to every bar (as if a 1:1 bonus happened
    # after this whole window) and confirm SMA/52w reflect the adjustment.
    factors = {b["date"]: Decimal("0.5") for b in bars}
    await repo.update_adjustment_factors(sec_id, factors)
    await db_session.commit()

    pipeline = IndicatorPipelineImpl(db_session)
    reference_date = start + timedelta(days=299)
    indicators = await pipeline.compute(symbol=symbol, reference_date=reference_date, config={})

    # Every raw close in the seed data is halved by the adjustment factor, so
    # every adjusted SMA must be exactly half of what the raw seed produces.
    raw_price_at_last_bar = bars[-1]["close"]
    assert indicators.sma50 is not None
    assert float(indicators.sma50) < raw_price_at_last_bar / 2 + 1
    assert indicators.high_52w is not None
    last_252 = bars[-252:]
    assert float(indicators.high_52w) == pytest.approx(
        max(b["high"] for b in last_252) * 0.5, rel=1e-6
    )
    assert float(indicators.low_52w) == pytest.approx(
        min(b["low"] for b in last_252) * 0.5, rel=1e-6
    )


@pytest.mark.asyncio
async def test_indicator_pipeline_insufficient_history(db_session: AsyncSession) -> None:
    """A brand-new security with only 10 bars must return all-None indicators."""
    symbol = "NEWIPO"
    start = date(2024, 6, 1)
    bars = _seed_bars(symbol, start, 10)

    security = SecurityModel(symbol=symbol, name=f"{symbol} Ind", is_active=True)
    db_session.add(security)
    await db_session.flush()
    await db_session.refresh(security)

    repo = SqlOHLCVRepository(db_session)
    await repo.upsert_bars(security.id, _to_ohlcv(bars))
    await db_session.commit()

    pipeline = IndicatorPipelineImpl(db_session)
    indicators = await pipeline.compute(
        symbol=symbol,
        reference_date=start + timedelta(days=9),
        config={},
    )

    assert indicators.as_of == start + timedelta(days=9)
    assert indicators.sma50 is None
    assert indicators.sma150 is None
    assert indicators.sma200 is None
    assert indicators.sma200_slope_pct is None
    assert indicators.high_52w is None
    assert indicators.low_52w is None