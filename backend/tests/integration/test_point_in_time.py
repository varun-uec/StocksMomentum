"""Point-in-time market data (ADR-014 §7, M14): look-ahead tests.

A decision on session D at data revision R sees bars dated by D as stored at
R, adjusted only by corporate actions known at R with an ex-date by D, and the
universe listed by D. Anything later is invisible or raises.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.application.use_cases.research.historical_screening import (
    HistoricalScreeningUseCase,
)
from momentum25.domain.entities.security import Security
from momentum25.domain.errors import LookAheadError
from momentum25.domain.value_objects.types import Symbol
from momentum25.infrastructure.calendar.nse_calendar import get_nse_trading_calendar
from momentum25.infrastructure.config.settings import get_settings
from momentum25.infrastructure.config.strategy_loader import load_strategies_dir
from momentum25.infrastructure.persistence.models import (
    CorporateActionModel,
    OHLCVDailyModel,
    SecurityModel,
)
from momentum25.infrastructure.persistence.point_in_time import (
    PointInTimeIndicatorPipeline,
    PointInTimeOHLCVRepository,
    PointInTimeSecurityRepository,
    PointInTimeSource,
    current_revision,
)
from momentum25.infrastructure.persistence.repositories.data_manifests import (
    SqlDataManifestRepository,
)
from momentum25.infrastructure.pipelines.indicator_pipeline import IndicatorPipelineImpl

START = date(2024, 1, 1)
DAYS = [START + timedelta(days=i) for i in range(500) if (START + timedelta(days=i)).weekday() < 5]
DECISION = DAYS[300]
EX_DATE = DAYS[320]  # a 1:1 bonus after the decision


async def _security(session: AsyncSession, symbol: str = "PIT", **fields: object) -> int:
    security = SecurityModel(symbol=symbol, name=symbol, isin="INE000000001", **fields)
    session.add(security)
    await session.flush()
    return security.id


async def _bars(session: AsyncSession, security_id: int, factor_before_ex: str = "1") -> None:
    """Raw prints near 100, halving at the bonus; the stored factor knows the bonus."""
    for i, day in enumerate(DAYS):
        raw = Decimal(100 + i % 5) if day < EX_DATE else Decimal(50 + i % 5)
        factor = Decimal(factor_before_ex) if day < EX_DATE else Decimal(1)
        session.add(
            OHLCVDailyModel(
                security_id=security_id,
                date=day,
                open=raw,
                high=raw,
                low=raw,
                close=raw,
                volume=1000,
                adj_factor=factor,
                adj_close=raw * factor,
            )
        )
    await session.commit()


async def _bonus(session: AsyncSession, security_id: int) -> None:
    session.add(
        CorporateActionModel(
            security_id=security_id, ex_date=EX_DATE, type="BONUS", ratio=Decimal("0.5")
        )
    )
    await session.commit()


async def test_a_later_bonus_does_not_reshape_earlier_prices(db_session: AsyncSession) -> None:
    sid = await _security(db_session)
    await _bars(db_session, sid, factor_before_ex="0.5")  # the live table knows the bonus
    await _bonus(db_session, sid)
    revision = await current_revision(db_session)

    before = PointInTimeSource(db_session, DECISION, revision)
    bars = await before.bars(sid, DECISION, 10)
    assert {b.adj_factor for b in bars} == {Decimal(1)}  # the bonus was not known
    assert bars[-1].adj_close == bars[-1].close

    after = PointInTimeSource(db_session, DAYS[-1], revision)
    early = (await after.bars(sid, DAYS[-1], 1000))[0]
    assert early.adj_factor == Decimal("0.5")  # past the ex-date, earlier bars are halved


async def test_no_bar_after_the_decision_is_ever_served(db_session: AsyncSession) -> None:
    sid = await _security(db_session)
    await _bars(db_session, sid)
    source = PointInTimeSource(db_session, DECISION, await current_revision(db_session))
    bars = await source.bars(sid, DECISION, 1000)
    assert bars[-1].date == DECISION and len(bars) == 301
    with pytest.raises(LookAheadError):
        await source.bars(sid, DECISION + timedelta(days=1), 10)
    with pytest.raises(LookAheadError):
        await PointInTimeOHLCVRepository(source).get_series(sid, 10, DAYS[-1])
    with pytest.raises(LookAheadError):
        await PointInTimeIndicatorPipeline(db_session, source).compute("PIT", DAYS[-1], {})


async def test_a_later_correction_is_invisible_at_the_earlier_revision(
    db_session: AsyncSession,
) -> None:
    sid = await _security(db_session)
    await _bars(db_session, sid)
    revision = await current_revision(db_session)
    await db_session.execute(
        update(OHLCVDailyModel)
        .where(OHLCVDailyModel.security_id == sid, OHLCVDailyModel.date == DECISION)
        .values(close=Decimal("999"))
    )
    await db_session.commit()
    then = await PointInTimeSource(db_session, DECISION, revision).bars(sid, DECISION, 1)
    now = await PointInTimeSource(db_session, DECISION, await current_revision(db_session)).bars(
        sid, DECISION, 1
    )
    assert then[0].close != Decimal("999") and now[0].close == Decimal("999")


async def test_rolled_back_correction_does_not_advance_committed_revision(
    db_session: AsyncSession,
) -> None:
    """Sequence gaps from aborted transactions must not change manifest identity."""
    sid = await _security(db_session, "ROLLBACK")
    await _bars(db_session, sid)
    before = await current_revision(db_session)

    await db_session.execute(
        update(OHLCVDailyModel)
        .where(OHLCVDailyModel.security_id == sid, OHLCVDailyModel.date == DECISION)
        .values(close=Decimal("999"))
    )
    await db_session.rollback()

    assert await current_revision(db_session) == before
    assert (await SqlDataManifestRepository(db_session).capture()).revision == before


async def test_an_action_recorded_after_the_revision_is_unknown(db_session: AsyncSession) -> None:
    sid = await _security(db_session)
    await _bars(db_session, sid)
    revision = await current_revision(db_session)
    await _bonus(db_session, sid)
    late = DAYS[-1]
    unknown = await PointInTimeSource(db_session, late, revision).bars(sid, late, 1000)
    known = await PointInTimeSource(db_session, late, await current_revision(db_session)).bars(
        sid, late, 400
    )
    assert unknown[0].adj_factor == Decimal(1) and known[0].adj_factor == Decimal("0.5")


async def test_the_universe_is_the_one_listed_at_the_decision(db_session: AsyncSession) -> None:
    await _security(db_session, "LISTED", listing_date=DAYS[0])
    await _security(db_session, "LATER", listing_date=DECISION + timedelta(days=1))
    await _security(db_session, "GONE", listing_date=DAYS[0], delisting_date=DECISION)
    # Delisted after the decision, and inactive today: it was trading then.
    await _security(
        db_session, "SURVIVOR", listing_date=DAYS[0], delisting_date=DAYS[-1], is_active=False
    )
    await db_session.commit()
    source = PointInTimeSource(db_session, DECISION, await current_revision(db_session))
    universe = await PointInTimeSecurityRepository(source).list_active()
    assert sorted(str(s.symbol) for s in universe) == ["LISTED", "SURVIVOR"]


async def test_a_name_inactive_today_still_has_bars_at_the_decision(
    db_session: AsyncSession,
) -> None:
    sid = await _security(db_session, delisting_date=DAYS[-1], is_active=False)
    await _bars(db_session, sid)
    source = PointInTimeSource(db_session, DECISION, await current_revision(db_session))
    indicators = await PointInTimeIndicatorPipeline(db_session, source).compute("PIT", DECISION, {})
    assert indicators.sma50 is not None
    # The live pipeline drops it: it reads today's is_active (ADR-014 Context §5).
    live = await IndicatorPipelineImpl(db_session).compute("PIT", DECISION, {})
    assert live.sma50 is None


async def test_without_corrections_point_in_time_matches_the_live_pipeline(
    db_session: AsyncSession,
) -> None:
    sid = await _security(db_session)
    await _bars(db_session, sid)
    source = PointInTimeSource(db_session, DECISION, await current_revision(db_session))
    pit = await PointInTimeIndicatorPipeline(db_session, source).compute("PIT", DECISION, {})
    live = await IndicatorPipelineImpl(db_session).compute("PIT", DECISION, {})
    assert pit == live


async def test_a_stored_manifest_rebuilds_the_inputs_it_recorded(
    db_session: AsyncSession,
) -> None:
    sid = await _security(db_session)
    await _bars(db_session, sid)
    manifests = SqlDataManifestRepository(db_session)
    manifest = await manifests.capture()
    assert await manifests.capture() == manifest  # idempotent: one row per hash
    await db_session.commit()
    seen = await PointInTimeSource(db_session, DECISION, manifest.revision).bars(sid, DECISION, 50)

    # A correction and a bonus arrive after the manifest was recorded.
    await db_session.execute(
        update(OHLCVDailyModel)
        .where(OHLCVDailyModel.security_id == sid, OHLCVDailyModel.date == DECISION)
        .values(close=Decimal("999"))
    )
    await _bonus(db_session, sid)

    stored = await manifests.get(manifest.data_version)
    assert stored is not None and stored == manifest
    rebuilt = await PointInTimeSource(db_session, DECISION, stored.revision).bars(sid, DECISION, 50)
    assert rebuilt == seen
    assert (await manifests.capture()).data_version != manifest.data_version


async def test_historical_screening_lets_a_look_ahead_fail_the_run(
    db_session: AsyncSession,
) -> None:
    sid = await _security(db_session)
    await _bars(db_session, sid)
    revision = await current_revision(db_session)
    source = PointInTimeSource(db_session, DECISION, revision)
    # RS ratings read through a later source, so the raise happens per symbol.
    later = PointInTimeSource(db_session, DAYS[-1], revision)
    screening = HistoricalScreeningUseCase(
        security_repo=None,
        ohlcv_repo=PointInTimeOHLCVRepository(later),
        screening_run_repo=None,
        strategy_repo=None,
        indicator_pipeline=PointInTimeIndicatorPipeline(db_session, source),
        strategy_engine=None,
        calendar=get_nse_trading_calendar(),
    )
    strategy = load_strategies_dir(Path(get_settings().strategy_dir))[0]
    with pytest.raises(LookAheadError):  # not swallowed as a per-symbol failure
        await screening.screen(
            strategy, DAYS[-1], [Security(symbol=Symbol("PIT"), name="PIT", id=sid)]
        )
