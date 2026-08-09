"""Integration tests for NSE Bhavcopy data ingestion.

Validates bhavcopy row parsing, holiday handling, and bulk idempotent persistence
via SQLAlchemy Core's upsert path. The ``nsemine`` scraping calls are mocked at
the module boundary (no live NSE access).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pandas as pd
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.infrastructure.adapters import BhavcopyProvider


def _bhavcopy_df(
    trade_date: date,
    symbols: list[tuple[str, str, str, str, str, int]],
) -> pd.DataFrame:
    """Build a bhavcopy-shaped DataFrame matching nsemine's standardized columns."""
    return pd.DataFrame(
        [
            {
                "date": trade_date,
                "symbol": sym,
                "series": "EQ",
                "previous_close": o,
                "open": o,
                "high": h,
                "low": lo,
                "close": c,
                "vwap": c,
                "volume": v,
                "turnover": 0.0,
                "delivery_volume": 0.0,
                "delivery_pct": 0.0,
            }
            for sym, o, h, lo, c, v in symbols
        ]
    )


async def _seed_security_id(session: AsyncSession, symbol: str) -> int:
    """Insert a security and return its PK."""
    from momentum25.infrastructure.persistence.models import SecurityModel

    model = SecurityModel(symbol=symbol, name=f"{symbol} Ind", is_active=True)
    session.add(model)
    await session.flush()
    await session.refresh(model)
    return model.id


@pytest.mark.asyncio
async def test_bhavcopy_stream_parses_equity_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """A bhavcopy response for the requested date must yield matching RawBars."""
    trade_date = date(2024, 6, 28)
    df = _bhavcopy_df(
        trade_date,
        [
            ("RELIANCE", "2500", "2520", "2490", "2510", 1234567),
            ("TCS", "4200", "4250", "4180", "4230", 987654),
        ],
    )
    monkeypatch.setattr(
        "momentum25.infrastructure.providers.bhavcopy.archives.get_daily_bhavcopy_and_deliverables_data",
        lambda **_kwargs: df,
    )
    provider = BhavcopyProvider()
    bars = await provider.fetch_eod(trade_date)
    assert len(bars) == 2
    assert {b.symbol for b in bars} == {"RELIANCE", "TCS"}
    assert bars[0].close == Decimal("2510")
    assert bars[0].volume == 1234567


@pytest.mark.asyncio
async def test_bhavcopy_holiday_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """A prior-session fallback (nsemine's holiday behaviour) must yield []."""
    requested = date(2024, 7, 15)
    stale = _bhavcopy_df(
        date(2024, 7, 12),  # nsemine silently returns the last trading session
        [("RELIANCE", "2500", "2520", "2490", "2510", 1234567)],
    )
    monkeypatch.setattr(
        "momentum25.infrastructure.providers.bhavcopy.archives.get_daily_bhavcopy_and_deliverables_data",
        lambda **_kwargs: stale,
    )
    provider = BhavcopyProvider()
    bars = await provider.fetch_eod(requested)
    assert bars == []


@pytest.mark.asyncio
async def test_bhavcopy_fetch_error_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """A raised exception from nsemine must return [] without propagating."""

    def _raise(**_kwargs: object) -> None:
        raise RuntimeError("NSE unavailable")

    monkeypatch.setattr(
        "momentum25.infrastructure.providers.bhavcopy.archives.get_daily_bhavcopy_and_deliverables_data",
        _raise,
    )
    provider = BhavcopyProvider()
    bars = await provider.fetch_eod(date(2024, 7, 15))
    assert bars == []


# ── Corporate-action adjustment persistence (Objective 1, Phase 1) ─────────


@pytest.mark.asyncio
async def test_update_adjustment_factors_persists_and_recomputes_adj_close(
    db_session: AsyncSession,
) -> None:
    """Persisting a factor must also recompute ``adj_close`` from the raw close."""
    from momentum25.domain.entities.market_data import OHLCVBar
    from momentum25.infrastructure.persistence.models import OHLCVDailyModel
    from momentum25.infrastructure.persistence.repositories.ohlcv import SqlOHLCVRepository

    security_id = await _seed_security_id(db_session, "WIPRO")
    repo = SqlOHLCVRepository(db_session)
    bars = [
        OHLCVBar(
            date=date(2026, 1, 1),
            open=Decimal("100"),
            high=Decimal("105"),
            low=Decimal("95"),
            close=Decimal("100"),
            volume=1000,
        ),
        OHLCVBar(
            date=date(2026, 1, 2),
            open=Decimal("200"),
            high=Decimal("205"),
            low=Decimal("195"),
            close=Decimal("200"),
            volume=2000,
        ),
    ]
    await repo.upsert_bars(security_id, bars)
    await db_session.commit()

    updated = await repo.update_adjustment_factors(
        security_id, {date(2026, 1, 1): Decimal("0.5"), date(2026, 1, 2): Decimal("1")}
    )
    await db_session.commit()
    assert updated == 2

    result = await db_session.execute(
        select(OHLCVDailyModel)
        .where(OHLCVDailyModel.security_id == security_id)
        .order_by(OHLCVDailyModel.date)
    )
    rows = result.scalars().all()
    assert rows[0].adj_factor == Decimal("0.5")
    assert rows[0].adj_close == Decimal("50.0000")  # 100 * 0.5
    assert rows[1].adj_factor == Decimal("1")
    assert rows[1].adj_close == Decimal("200.0000")


@pytest.mark.asyncio
async def test_upsert_bars_batch_writes_across_securities_and_updates(
    db_session: AsyncSession,
) -> None:
    """A single batch upsert must persist many securities and be idempotent."""
    from momentum25.domain.entities.market_data import OHLCVBar
    from momentum25.infrastructure.persistence.models import OHLCVDailyModel
    from momentum25.infrastructure.persistence.repositories.ohlcv import SqlOHLCVRepository

    security_a = await _seed_security_id(db_session, "RELIANCE")
    security_b = await _seed_security_id(db_session, "TCS")
    repo = SqlOHLCVRepository(db_session)

    def _bar(close: str, volume: int, bar_date: date) -> OHLCVBar:
        return OHLCVBar(
            date=bar_date,
            open=Decimal(close),
            high=Decimal(close),
            low=Decimal(close),
            close=Decimal(close),
            volume=volume,
        )

    written = await repo.upsert_bars_batch(
        {
            security_a: [
                _bar("100", 1000, date(2026, 2, 1)),
                _bar("200", 2000, date(2026, 2, 2)),
            ],
            security_b: [_bar("300", 3000, date(2026, 2, 1))],
        }
    )
    await db_session.commit()
    assert written == 3

    total = (
        await db_session.execute(select(OHLCVDailyModel))
    ).scalars().all()
    assert len(total) == 3
    assert {r.security_id for r in total} == {security_a, security_b}

    # Re-write with a changed close: ON CONFLICT must update, not duplicate.
    await repo.upsert_bars_batch({security_a: [_bar("150", 1500, date(2026, 2, 1))]})
    await db_session.commit()
    rows = (
        await db_session.execute(
            select(OHLCVDailyModel)
            .execution_options(populate_existing=True)
            .where(OHLCVDailyModel.security_id == security_a)
        )
    ).scalars().all()
    assert len(rows) == 2
    assert {float(r.close) for r in rows} == {150.0, 200.0}


@pytest.mark.asyncio
async def test_upsert_bars_equivalent_to_batch_single(
    db_session: AsyncSession,
) -> None:
    """The per-security method must behave exactly like a one-key batch call."""
    from momentum25.domain.entities.market_data import OHLCVBar
    from momentum25.infrastructure.persistence.repositories.ohlcv import SqlOHLCVRepository

    security_id = await _seed_security_id(db_session, "INFY")
    repo = SqlOHLCVRepository(db_session)
    bar = OHLCVBar(
        date=date(2026, 2, 1),
        open=Decimal("100"),
        high=Decimal("105"),
        low=Decimal("95"),
        close=Decimal("100"),
        volume=1000,
    )
    assert await repo.upsert_bars(security_id, [bar]) == 1
    await db_session.commit()
    assert await repo.upsert_bars_batch({security_id: [bar]}) == 1
    await db_session.commit()


@pytest.mark.asyncio
async def test_corporate_action_repository_upsert_is_idempotent(
    db_session: AsyncSession,
) -> None:
    """Re-saving the same (security, ex_date, type) must update, not duplicate."""
    from momentum25.domain.ports.market_data import RawCorporateAction
    from momentum25.infrastructure.persistence.repositories.corporate_actions import (
        SqlCorporateActionRepository,
    )

    security_id = await _seed_security_id(db_session, "HDFCBANK")
    repo = SqlCorporateActionRepository(db_session)

    action = RawCorporateAction(
        symbol="HDFCBANK",
        ex_date=date(2026, 3, 1),
        action_type="bonus",
        ratio=Decimal("0.5"),
        raw_subject="Bonus 1:1",
    )
    written = await repo.save_many(security_id, [action])
    await db_session.commit()
    assert written == 1

    # Re-save with a corrected ratio for the same (security, ex_date, type).
    corrected = RawCorporateAction(
        symbol="HDFCBANK",
        ex_date=date(2026, 3, 1),
        action_type="bonus",
        ratio=Decimal("0.6"),
        raw_subject="Bonus 1:1 (corrected)",
    )
    await repo.save_many(security_id, [corrected])
    await db_session.commit()

    actions = await repo.list_for_security(security_id)
    assert len(actions) == 1
    assert actions[0].ratio == Decimal("0.6")
    assert actions[0].raw_subject == "Bonus 1:1 (corrected)"


# ── Security listing_date upsert (Objective 3) ─────────────────────────────


@pytest.mark.asyncio
async def test_upsert_securities_does_not_clobber_known_listing_date(
    db_session: AsyncSession,
) -> None:
    """A later upsert without a listing_date must not erase an already-known one."""
    from momentum25.domain.entities.security import Security
    from momentum25.domain.value_objects.types import Symbol
    from momentum25.infrastructure.persistence.repositories.security import (
        SqlSecurityRepository,
    )

    repo = SqlSecurityRepository(db_session)

    await repo.upsert_many(
        [Security(symbol=Symbol("INFY"), name="Infosys", listing_date=date(1995, 6, 8))]
    )
    await db_session.commit()

    # A daily screening run that only knows the bare symbol (no instrument
    # master lookup available) must not wipe out the listing_date.
    await repo.upsert_many([Security(symbol=Symbol("INFY"), name="INFY")])
    await db_session.commit()

    security = await repo.get_by_symbol("INFY")
    assert security is not None
    assert security.listing_date == date(1995, 6, 8)


# ``PriceRepository`` / bulk tests live in tests/unit/.
# Integration tests for repository behaviour against Postgres require the
# docker-compose test container and are added in milestone M1/M2.
