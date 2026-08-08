"""Integration tests for the RP-012 Phase 2 overlap backfill and gates.

Exercises the real repositories against the test database: the legacy staging
table coexists with the live ``ohlcv_daily`` for the same (security, date), Gate
4a reconciliation joins them, the liquidity floor reconstructs an immutable
``historical_universe``, Gate 4d calibrates it, and the C1/C2 validation-gap
logs are written.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.application.use_cases.research.historical_universe_reconstruction import (
    HistoricalUniverseReconstruction,
)
from momentum25.application.use_cases.research.legacy_overlap_backfill import (
    LegacyOverlapBackfill,
)
from momentum25.application.use_cases.research.overlap_reconciliation_report import (
    OverlapReconciliationReport,
)
from momentum25.domain.entities.market_data import OHLCVBar
from momentum25.domain.ports.market_data import RawBar
from momentum25.infrastructure.persistence.models import SecurityModel
from momentum25.infrastructure.persistence.repositories.historical_backfill import (
    SqlHistoricalUniverseRepository,
    SqlLegacyOHLCVRepository,
    SqlValidationGapLogRepository,
)
from momentum25.infrastructure.persistence.repositories.ohlcv import SqlOHLCVRepository
from momentum25.infrastructure.persistence.repositories.security import (
    SqlSecurityRepository,
)

_START = date(2019, 9, 30)


class _FakeProvider:
    """Returns pre-seeded legacy RawBars per date; empty for non-trading days."""

    def __init__(self, bars_by_date: dict[date, list[RawBar]]) -> None:
        self._bars = bars_by_date

    async def fetch_eod_from_legacy_archive(self, for_date: date) -> list[RawBar]:
        return self._bars.get(for_date, [])


def _sessions(n: int) -> list[date]:
    """Return ``n`` consecutive daily dates starting at the overlap start."""
    return [_START + timedelta(days=i) for i in range(n)]


async def _seed_security(
    session: AsyncSession,
    symbol: str,
    isin: str | None = None,
    *,
    is_active: bool = True,
    listing_date: date | None = None,
    delisting_date: date | None = None,
) -> int:
    sec = SecurityModel(
        symbol=symbol,
        name=symbol,
        isin=isin,
        is_active=is_active,
        listing_date=listing_date,
        delisting_date=delisting_date,
    )
    session.add(sec)
    await session.flush()
    assert sec.id is not None
    return sec.id


async def test_backfill_period_correct_reattributes_chain_members(
    db_session: AsyncSession,
) -> None:
    # A rename chain: OLD (delisted) and NEW (active successor) share one ISIN.
    # A legacy bar printed under OLD's ticker on a date inside OLD's interval
    # must attach to OLD's id, not collapse onto the active successor NEW — and
    # a bar printed under NEW's ticker after the handoff attaches to NEW.
    isin = "INE111C01011"
    old_id = await _seed_security(
        db_session,
        "OLDNAME",
        isin=isin,
        is_active=False,
        listing_date=date(2015, 1, 1),
        delisting_date=date(2021, 3, 31),
    )
    new_id = await _seed_security(
        db_session,
        "NEWNAME",
        isin=isin,
        is_active=True,
        listing_date=date(2021, 4, 1),
    )
    await db_session.commit()

    old_day = date(2020, 6, 1)
    new_day = date(2021, 6, 1)

    def _bar(symbol: str, d: date) -> RawBar:
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
            isin=isin,
        )

    bars_by_date = {
        old_day: [_bar("OLDNAME", old_day)],
        new_day: [_bar("NEWNAME", new_day)],
    }
    backfill = LegacyOverlapBackfill(
        provider=_FakeProvider(bars_by_date),
        security_repo=SqlSecurityRepository(db_session),
        legacy_repo=SqlLegacyOHLCVRepository(db_session),
        gap_log_repo=SqlValidationGapLogRepository(db_session),
    )
    summary = await backfill.execute(start=old_day, end=new_day)
    await db_session.commit()

    assert summary.period_correct_resolved == 2
    assert summary.isin_resolved == 0  # chain members never take the ISIN path

    legacy_repo = SqlLegacyOHLCVRepository(db_session)
    assert set(await legacy_repo.bars_by_security_on(old_day)) == {old_id}
    assert set(await legacy_repo.bars_by_security_on(new_day)) == {new_id}


async def test_backfill_resolution_paths_isin_symbol_and_unresolved(
    db_session: AsyncSession,
) -> None:
    # DRIFTED: master lists NEWTICK/ISIN-A, legacy row still uses OLDTICK — must
    # be recovered by ISIN. STABLE: no ISIN drift → symbol fallback. GHOST: not
    # in the master at all → unresolved.
    drifted_id = await _seed_security(db_session, "NEWTICK", isin="INE000A01011")
    stable_id = await _seed_security(db_session, "STABLE", isin="INE000B01022")
    await db_session.commit()

    d = _START

    def _bar(symbol: str, isin: str | None) -> RawBar:
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
            isin=isin,
        )

    bars_by_date = {
        d: [
            _bar("OLDTICK", "INE000A01011"),  # ISIN-resolved despite ticker drift
            _bar("STABLE", None),  # symbol fallback (no ISIN on the row)
            _bar("GHOST", "INE999Z09099"),  # unresolved: neither ISIN nor symbol
        ]
    }
    backfill = LegacyOverlapBackfill(
        provider=_FakeProvider(bars_by_date),
        security_repo=SqlSecurityRepository(db_session),
        legacy_repo=SqlLegacyOHLCVRepository(db_session),
        gap_log_repo=SqlValidationGapLogRepository(db_session),
    )
    summary = await backfill.execute(start=d, end=d)
    await db_session.commit()

    assert summary.isin_resolved == 1
    assert summary.symbol_fallback_resolved == 1
    assert summary.unresolved == 1
    assert summary.unknown_symbols_skipped == 1  # back-compat: == unresolved
    assert summary.unknown_symbols == {"GHOST"}
    assert summary.rows_written == 2  # only resolved rows persisted

    legacy = await SqlLegacyOHLCVRepository(db_session).bars_by_security_on(d)
    assert set(legacy) == {drifted_id, stable_id}


async def test_backfill_persists_legacy_without_touching_live(db_session: AsyncSession) -> None:
    sec_id = await _seed_security(db_session, "ACME")
    await db_session.commit()

    dates = _sessions(3)
    bars_by_date = {
        d: [
            RawBar(
                symbol="ACME",
                date=d,
                open=Decimal("100"),
                high=Decimal("101"),
                low=Decimal("99"),
                close=Decimal("100"),
                volume=1000,
                prev_close=Decimal("100"),
                turnover_value=Decimal("100000"),
            )
        ]
        for d in dates
    }
    provider = _FakeProvider(bars_by_date)
    backfill = LegacyOverlapBackfill(
        provider=provider,
        security_repo=SqlSecurityRepository(db_session),
        legacy_repo=SqlLegacyOHLCVRepository(db_session),
        gap_log_repo=SqlValidationGapLogRepository(db_session),
    )
    summary = await backfill.execute(start=dates[0], end=dates[-1])
    await db_session.commit()

    assert summary.trading_days == 3
    assert summary.rows_written == 3
    # Live ohlcv_daily is untouched by the backfill.
    assert await SqlOHLCVRepository(db_session).bars_by_security_on(dates[0]) == {}
    legacy = await SqlLegacyOHLCVRepository(db_session).bars_by_security_on(dates[0])
    assert set(legacy) == {sec_id}


async def test_backfill_rejects_pre_cutover_window(db_session: AsyncSession) -> None:
    backfill = LegacyOverlapBackfill(
        provider=_FakeProvider({}),
        security_repo=SqlSecurityRepository(db_session),
        legacy_repo=SqlLegacyOHLCVRepository(db_session),
        gap_log_repo=SqlValidationGapLogRepository(db_session),
    )
    import pytest

    # Default floor (OVERLAP_START) still rejects an accidental pre-cutover run.
    with pytest.raises(ValueError, match="precedes the permitted floor"):
        await backfill.execute(start=date(2019, 9, 29), end=date(2019, 9, 30))

    # An explicit lower floor (authorized Phase 3) permits the same start.
    with pytest.raises(ValueError, match="precedes the permitted floor"):
        await backfill.execute(
            start=date(1994, 11, 2),
            end=date(1994, 11, 3),
            floor=date(1994, 11, 3),
        )


async def test_reconciliation_matches_and_flags(db_session: AsyncSession) -> None:
    sec_id = await _seed_security(db_session, "ACME")
    legacy_repo = SqlLegacyOHLCVRepository(db_session)
    ohlcv_repo = SqlOHLCVRepository(db_session)
    d = _START

    bar = OHLCVBar(
        date=d, open=Decimal("10"), high=Decimal("10"), low=Decimal("10"),
        close=Decimal("10"), volume=500, prev_close=Decimal("10"),
        turnover_value=Decimal("5000"),
    )
    await legacy_repo.upsert_bars(sec_id, [bar])
    await ohlcv_repo.upsert_bars(sec_id, [bar])
    await db_session.commit()

    report = await OverlapReconciliationReport(legacy_repo, ohlcv_repo).execute(d, d)
    assert report["joined_pairs"] == 1
    assert report["gate_passes"] is True
    assert report["close_match_rate"] == "1"


async def test_reconstruction_and_calibration(db_session: AsyncSession) -> None:
    sec_id = await _seed_security(db_session, "LIQUID")
    legacy_repo = SqlLegacyOHLCVRepository(db_session)
    universe_repo = SqlHistoricalUniverseRepository(db_session)

    # 260 sessions: 259 prior + the as_of date, all with turnover well above floor.
    dates = _sessions(260)
    bars = [
        OHLCVBar(
            date=d, open=Decimal("50"), high=Decimal("50"), low=Decimal("50"),
            close=Decimal("50"), volume=100000,
            prev_close=Decimal("50"), turnover_value=Decimal("20000000"),
        )
        for d in dates
    ]
    await legacy_repo.upsert_bars(sec_id, bars)
    await db_session.commit()

    recon = HistoricalUniverseReconstruction(legacy_repo, universe_repo)
    as_of = dates[-1]
    memberships = await recon.reconstruct_date(as_of)
    assert len(memberships) == 1
    assert memberships[0].eligible is True

    await universe_repo.insert_memberships(as_of, memberships)
    await db_session.commit()

    calibration = await recon.calibrate({as_of: {sec_id}})
    assert calibration["pooled_coverage"] == "1.0000"
    assert calibration["pooled_count_ratio"] == "1.0000"

    pit = await recon.verify_point_in_time(as_of)
    assert pit["no_lookahead"] is True


async def test_reconstruction_rejects_insufficient_history(db_session: AsyncSession) -> None:
    sec_id = await _seed_security(db_session, "YOUNG")
    legacy_repo = SqlLegacyOHLCVRepository(db_session)

    dates = _sessions(60)  # far fewer than 252 prior sessions
    bars = [
        OHLCVBar(
            date=d, open=Decimal("50"), high=Decimal("50"), low=Decimal("50"),
            close=Decimal("50"), volume=100000,
            prev_close=Decimal("50"), turnover_value=Decimal("20000000"),
        )
        for d in dates
    ]
    await legacy_repo.upsert_bars(sec_id, bars)
    await db_session.commit()

    memberships = await HistoricalUniverseReconstruction(
        legacy_repo, SqlHistoricalUniverseRepository(db_session)
    ).reconstruct_date(dates[-1])
    assert memberships[0].eligible is False
    assert memberships[0].reason == "insufficient_history"
