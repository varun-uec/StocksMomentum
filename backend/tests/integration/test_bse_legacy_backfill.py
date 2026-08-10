"""Integration tests for the RP-014 BSE legacy backfill.

Exercises the real repositories against the test database: the SC_CODE → ISIN
junction is learned from fake UDiFF-era instrument masters (first observation
wins, re-runs idempotent), bars resolve strictly through junction → ISIN →
canonical securities (never a name fallback), unresolved scrips are counted and
disclosed, and rows land in ``bse_legacy_ohlcv_daily`` — never the live
``ohlcv_daily`` or the NSE ``legacy_ohlcv_daily``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.application.use_cases.research.bse_legacy_backfill import (
    BseLegacyBackfill,
)
from momentum25.domain.ports.market_data import RawBar, RawInstrument
from momentum25.infrastructure.persistence.models import (
    BSELegacyOHLCVDailyModel,
    BSEScripJunctionModel,
    LegacyOHLCVDailyModel,
    OHLCVDailyModel,
    SecurityModel,
)
from momentum25.infrastructure.persistence.repositories.historical_backfill import (
    SqlBSEScripJunctionRepository,
    SqlLegacyOHLCVRepository,
)
from momentum25.infrastructure.persistence.repositories.security import (
    SqlSecurityRepository,
)

_START = date(2006, 3, 1)


class _FakeProvider:
    """Serves pre-seeded legacy bars and UDiFF-era instrument masters."""

    def __init__(
        self,
        bars_by_date: dict[date, list[RawBar]],
        masters_by_session: dict[date, list[RawInstrument]],
    ) -> None:
        self._bars = bars_by_date
        self._masters = masters_by_session

    async def fetch_eod(self, for_date: date) -> list[RawBar]:
        return self._bars.get(for_date, [])

    async def fetch_instrument_master(self, for_date: date) -> list[RawInstrument]:
        return self._masters.get(for_date, [])


def _raw_bar(symbol: str, native_code: str, d: date) -> RawBar:
    return RawBar(
        symbol=symbol,
        date=d,
        open=Decimal("10"),
        high=Decimal("10"),
        low=Decimal("10"),
        close=Decimal("10"),
        volume=100,
        prev_close=Decimal("10"),
        turnover_value=Decimal("1000"),
        native_code=native_code,
    )


async def _seed_security(
    session: AsyncSession,
    symbol: str,
    isin: str,
) -> int:
    sec = SecurityModel(symbol=symbol, name=symbol, isin=isin, is_active=True)
    session.add(sec)
    await session.flush()
    assert sec.id is not None
    return sec.id


async def _build(session: AsyncSession):
    """Seed a canonical security and a provider the backfill can resolve."""
    sec_id = await _seed_security(session, "ACME", "INE123A01012")
    await session.commit()

    d = _START
    bars = {d: [_raw_bar("ACME ", "500325", d)]}
    masters = {
        date(2024, 1, 2): [
            RawInstrument(
                symbol="ACME",
                name="ACME CORP LTD",
                isin="INE123A01012",
                series="A",
                native_code="500325",
            )
        ]
    }
    provider = _FakeProvider(bars, masters)
    bse_repo = SqlLegacyOHLCVRepository(session, model_cls=BSELegacyOHLCVDailyModel)
    backfill = BseLegacyBackfill(
        provider=provider,
        security_repo=SqlSecurityRepository(session),
        bse_repo=bse_repo,
        junction_repo=SqlBSEScripJunctionRepository(session),
    )
    return backfill, bse_repo, sec_id, d


async def test_backfill_learns_junction_and_resolves_strictly(
    db_session: AsyncSession,
) -> None:
    backfill, bse_repo, sec_id, d = await _build(db_session)

    summary = await backfill.execute(start=d, end=d)
    await db_session.commit()

    assert summary.junction_rows == 1
    assert summary.junction_mapped_to_canonical == 1
    assert summary.trading_days == 1
    assert summary.isin_resolved == 1
    assert summary.rows_written == 1
    assert summary.unresolved == 0

    # The bar landed on the BSE staging table, keyed to the canonical security.
    bars = await bse_repo.bars_by_security_on(d)
    assert set(bars) == {sec_id}
    assert bars[sec_id].close == Decimal("10")


async def test_backfill_staging_is_isolated_from_other_tables(
    db_session: AsyncSession,
) -> None:
    backfill, bse_repo, sec_id, d = await _build(db_session)
    await backfill.execute(start=d, end=d)
    await db_session.commit()

    for model in (OHLCVDailyModel, LegacyOHLCVDailyModel):
        count = await db_session.execute(select(func.count()).select_from(model))
        assert count.scalar_one() == 0


async def test_backfill_rerun_is_idempotent(db_session: AsyncSession) -> None:
    backfill, bse_repo, sec_id, d = await _build(db_session)
    await backfill.execute(start=d, end=d)
    await backfill.execute(start=d, end=d)
    await db_session.commit()

    rows = (
        await db_session.execute(
            select(BSELegacyOHLCVDailyModel).where(BSELegacyOHLCVDailyModel.date == d)
        )
    ).scalars().all()
    assert len(rows) == 1
    junction = await db_session.execute(select(BSEScripJunctionModel))
    assert len(junction.scalars().all()) == 1


async def test_junction_is_first_observation_wins(db_session: AsyncSession) -> None:
    # A later session disclosing a different ISIN must not overwrite the first.
    backfill, bse_repo, sec_id, d = await _build(db_session)
    await backfill.execute(start=d, end=d)

    provider = _FakeProvider(
        {},
        {
            date(2025, 1, 2): [
                RawInstrument(
                    symbol="ACME",
                    name="ACME CORP LTD",
                    isin="INE999Z09999",
                    series="A",
                    native_code="500325",
                )
            ]
        },
    )
    backfill2 = BseLegacyBackfill(
        provider=provider,
        security_repo=SqlSecurityRepository(db_session),
        bse_repo=bse_repo,
        junction_repo=SqlBSEScripJunctionRepository(db_session),
    )
    await backfill2.execute(start=d, end=d)
    await db_session.commit()

    junction = (
        await db_session.execute(
            select(BSEScripJunctionModel).where(
                BSEScripJunctionModel.sc_code == "500325"
            )
        )
    ).scalar_one()
    assert junction.isin == "INE123A01012"


async def test_backfill_counts_and_discloses_unresolvable_scrips(
    db_session: AsyncSession,
) -> None:
    # GHOST is traded in 2006 but never reappears in a UDiFF session (delisted
    # before 2024): junction-miss, resolved nothing, disclosed by name.
    d = _START
    bars = {d: [_raw_bar("GHOST ", "999999", d)]}
    provider = _FakeProvider(bars, {date(2024, 1, 2): []})
    backfill = BseLegacyBackfill(
        provider=provider,
        security_repo=SqlSecurityRepository(db_session),
        bse_repo=SqlLegacyOHLCVRepository(db_session, model_cls=BSELegacyOHLCVDailyModel),
        junction_repo=SqlBSEScripJunctionRepository(db_session),
    )
    summary = await backfill.execute(start=d, end=d)
    await db_session.commit()

    assert summary.isin_resolved == 0
    assert summary.unresolved == 1
    assert summary.rows_written == 0
    assert summary.unknown_scrips == {"GHOST "}


async def test_backfill_rejects_out_of_bounds_windows(db_session: AsyncSession) -> None:
    import pytest

    backfill = BseLegacyBackfill(
        provider=_FakeProvider({}, {}),
        security_repo=SqlSecurityRepository(db_session),
        bse_repo=SqlLegacyOHLCVRepository(db_session, model_cls=BSELegacyOHLCVDailyModel),
        junction_repo=SqlBSEScripJunctionRepository(db_session),
    )
    with pytest.raises(ValueError, match="precedes the BSE archive inception"):
        await backfill.execute(start=date(2006, 2, 28), end=_START)
    with pytest.raises(ValueError, match="precede the UDiFF era"):
        await backfill.execute(start=_START, end=date(2024, 1, 2))
