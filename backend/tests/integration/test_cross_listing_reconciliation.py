"""Integration tests for ReconcileCrossListings (Phase 5.1).

Proves the exchange dimension is persisted on the canonical security, that no
duplicate row is created for a cross-listed company, and — critically — that a
subsequent ordinary daily upsert (which does not know the exchange) cannot demote
a cross-listed security back to ``NSE``.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.application.use_cases.research.reconcile_cross_listings import (
    ReconcileCrossListings,
)
from momentum25.domain.entities.security import Security
from momentum25.domain.ports.market_data import RawInstrument
from momentum25.domain.value_objects.types import Symbol
from momentum25.infrastructure.persistence.models import SecurityModel
from momentum25.infrastructure.persistence.repositories.security import SqlSecurityRepository


class _FakeNSEProvider:
    def __init__(self, instruments: list[RawInstrument]) -> None:
        self._instruments = instruments

    async def fetch_instrument_master(self) -> list[RawInstrument]:
        return self._instruments


class _FakeBSEProvider:
    def __init__(self, instruments: list[RawInstrument]) -> None:
        self._instruments = instruments

    async def fetch_instrument_master(self, for_date: date | None = None) -> list[RawInstrument]:
        return self._instruments


NSE_MASTER = [
    RawInstrument(
        symbol="RELIANCE",
        name="Reliance Industries Ltd",
        isin="INE002A01018",
        series="EQ",
        listing_date=date(1995, 11, 29),
    ),
    RawInstrument(symbol="NSEONLY", name="NSE Only Ltd", isin="INE111A01011", series="EQ"),
]
BSE_MASTER = [
    RawInstrument(
        symbol="RELIANCE", name="RELIANCE INDUSTRIES LTD.", isin="INE002A01018", series="A"
    ),
    RawInstrument(symbol="BSEONLY", name="BSE Only Ltd", isin="INE777A01010", series="A"),
]


async def _rows(session: AsyncSession) -> dict[str, SecurityModel]:
    result = await session.execute(select(SecurityModel))
    return {row.symbol: row for row in result.scalars().all()}


@pytest.mark.asyncio
async def test_cross_listed_company_is_one_row_marked_both(db_session: AsyncSession) -> None:
    use_case = ReconcileCrossListings(
        nse_provider=_FakeNSEProvider(NSE_MASTER),
        bse_provider=_FakeBSEProvider(BSE_MASTER),
        security_repo=SqlSecurityRepository(db_session),
    )

    summary = await use_case.execute(as_of=date(2026, 8, 6))
    rows = await _rows(db_session)

    assert summary["cross_listed"] == 1
    assert summary["bse_only_withheld"] == 1
    assert set(rows) == {"RELIANCE", "NSEONLY"}
    assert rows["RELIANCE"].exchange == "BOTH"
    assert rows["RELIANCE"].isin == "INE002A01018"
    assert rows["RELIANCE"].name == "Reliance Industries Ltd"
    assert rows["NSEONLY"].exchange == "NSE"


@pytest.mark.asyncio
async def test_a_later_daily_upsert_cannot_demote_a_cross_listed_security(
    db_session: AsyncSession,
) -> None:
    repo = SqlSecurityRepository(db_session)
    await ReconcileCrossListings(
        nse_provider=_FakeNSEProvider(NSE_MASTER),
        bse_provider=_FakeBSEProvider(BSE_MASTER),
        security_repo=repo,
    ).execute(as_of=date(2026, 8, 6))

    # The daily screening pipeline upserts securities without knowing the
    # exchange (Security.exchange defaults to "NSE").
    await repo.upsert_many(
        [Security(symbol=Symbol("RELIANCE"), name="Reliance Industries Ltd", is_active=True)]
    )
    await db_session.commit()

    rows = await _rows(db_session)
    assert rows["RELIANCE"].exchange == "BOTH"


@pytest.mark.asyncio
async def test_whitelisted_bse_only_name_is_admitted_as_its_own_security(
    db_session: AsyncSession,
) -> None:
    use_case = ReconcileCrossListings(
        nse_provider=_FakeNSEProvider(NSE_MASTER),
        bse_provider=_FakeBSEProvider(BSE_MASTER),
        security_repo=SqlSecurityRepository(db_session),
        admit_bse_only_series=frozenset({"A"}),
    )

    summary = await use_case.execute(as_of=date(2026, 8, 6))
    rows = await _rows(db_session)

    assert summary["bse_only_admitted"] == 1
    assert rows["BSEONLY"].exchange == "BSE"
    assert rows["BSEONLY"].isin == "INE777A01010"


@pytest.mark.asyncio
async def test_empty_bse_master_writes_nothing_rather_than_demoting_everything(
    db_session: AsyncSession,
) -> None:
    repo = SqlSecurityRepository(db_session)
    await ReconcileCrossListings(
        nse_provider=_FakeNSEProvider(NSE_MASTER),
        bse_provider=_FakeBSEProvider(BSE_MASTER),
        security_repo=repo,
    ).execute(as_of=date(2026, 8, 6))

    summary = await ReconcileCrossListings(
        nse_provider=_FakeNSEProvider(NSE_MASTER),
        bse_provider=_FakeBSEProvider([]),
        security_repo=repo,
    ).execute(as_of=date(2026, 8, 8))

    rows = await _rows(db_session)
    assert summary == {"skipped": True, "reason": "empty_bse_master", "nse_master_size": 2}
    assert rows["RELIANCE"].exchange == "BOTH"
