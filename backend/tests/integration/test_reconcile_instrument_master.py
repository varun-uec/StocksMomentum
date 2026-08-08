"""Integration tests for ReconcileInstrumentMaster.

Discovered 2026-07-02: ``upsert_many`` never deactivates a security that's
been delisted/merged/renamed (absent from a fresh instrument-master fetch)
-- it only touches symbols present in the fetch. This left hundreds of
securities marked active in the database indefinitely after they left the
real exchange. These tests prove the reconciliation use case correctly
identifies and deactivates exactly the symbols missing from a fresh fetch,
and touches nothing else.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.application.use_cases.research.reconcile_instrument_master import (
    ReconcileInstrumentMaster,
)
from momentum25.domain.ports.market_data import RawInstrument
from momentum25.infrastructure.persistence.models import SecurityModel
from momentum25.infrastructure.persistence.repositories.security import SqlSecurityRepository


class _FakeMarketDataProvider:
    def __init__(self, current_symbols: list[str]) -> None:
        self._current_symbols = current_symbols

    async def fetch_instrument_master(self) -> list[RawInstrument]:
        return [
            RawInstrument(symbol=sym, name=f"{sym} Ltd", listing_date=date(2015, 1, 1))
            for sym in self._current_symbols
        ]


async def _seed_security(
    session: AsyncSession, symbol: str, name: str = "", is_active: bool = True
) -> int:
    model = SecurityModel(symbol=symbol, name=name or f"{symbol} Ltd", is_active=is_active)
    session.add(model)
    await session.flush()
    await session.refresh(model)
    return model.id


@pytest.mark.asyncio
async def test_deactivates_only_symbols_absent_from_current_master(
    db_session: AsyncSession,
) -> None:
    await _seed_security(db_session, "STAYS", name="Stays Active Ltd")
    await _seed_security(db_session, "MERGED", name="Merged Away Ltd")
    await _seed_security(db_session, "DELISTED", name="Delisted Ltd")
    await db_session.commit()

    security_repo = SqlSecurityRepository(db_session)
    use_case = ReconcileInstrumentMaster(
        market_data_provider=_FakeMarketDataProvider(["STAYS"]),
        security_repo=security_repo,
    )

    summary = await use_case.execute()

    assert summary == {
        "active_before": 3,
        "current_master_size": 1,
        "deactivated": 2,
    }

    result = await db_session.execute(
        select(SecurityModel.symbol, SecurityModel.is_active, SecurityModel.name)
    )
    rows = {r.symbol: (r.is_active, r.name) for r in result}
    assert rows["STAYS"][0] is True
    assert rows["MERGED"][0] is False
    assert rows["DELISTED"][0] is False

    # The real company name must survive deactivation -- not clobbered with a
    # placeholder just because the provider no longer lists the symbol.
    assert rows["MERGED"][1] == "Merged Away Ltd"
    assert rows["DELISTED"][1] == "Delisted Ltd"


@pytest.mark.asyncio
async def test_already_inactive_securities_are_not_recounted(
    db_session: AsyncSession,
) -> None:
    await _seed_security(db_session, "ALREADYGONE", is_active=False)
    await _seed_security(db_session, "STILLHERE", is_active=True)
    await db_session.commit()

    security_repo = SqlSecurityRepository(db_session)
    use_case = ReconcileInstrumentMaster(
        market_data_provider=_FakeMarketDataProvider(["STILLHERE"]),
        security_repo=security_repo,
    )

    summary = await use_case.execute()

    # Only the currently-active set is considered -- an already-inactive
    # security contributes nothing to deactivate.
    assert summary["active_before"] == 1
    assert summary["deactivated"] == 0
