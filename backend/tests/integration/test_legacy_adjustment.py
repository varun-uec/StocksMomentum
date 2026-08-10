"""Integration tests for backward price adjustment on the legacy staging tables.

The legacy tables held raw prints, so a split or bonus read as a fake
single-day collapse. RELIANCE's 1:1 bonus (ex-date 2017-09-07) showed as
-50.3%. These tests pin the fix: the legacy repository applies the *same*
adjustment the live ``ohlcv_daily`` path applies, for both the NSE and the BSE
staging table, and re-ingesting a bar never wipes the adjusted close.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.domain.entities.market_data import (
    OHLCVBar,
    compute_adjustment_factors,
)
from momentum25.domain.ports.market_data import RawCorporateAction
from momentum25.infrastructure.persistence.models import (
    BSELegacyOHLCVDailyModel,
    LegacyOHLCVDailyModel,
    SecurityModel,
)
from momentum25.infrastructure.persistence.repositories.historical_backfill import (
    SqlLegacyOHLCVRepository,
)

_MODELS = [LegacyOHLCVDailyModel, BSELegacyOHLCVDailyModel]

# RELIANCE's real closes around the 1:1 bonus, ex-date 2017-09-07.
_CLOSES = {
    date(2017, 9, 6): Decimal("1645.40"),
    date(2017, 9, 7): Decimal("818.10"),
}
_BONUS = RawCorporateAction(
    symbol="RELIANCE",
    ex_date=date(2017, 9, 7),
    action_type="bonus",
    ratio=Decimal("0.5"),
    raw_subject="Bonus 1:1",
)


async def _seed(session: AsyncSession) -> int:
    sec = SecurityModel(
        symbol="RELIANCE", name="RELIANCE", isin="INE002A01018", is_active=True
    )
    session.add(sec)
    await session.flush()
    assert sec.id is not None
    return sec.id


def _bar(d: date, close: Decimal) -> OHLCVBar:
    return OHLCVBar(
        date=d,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=100,
        prev_close=close,
        turnover_value=Decimal("1000"),
    )


@pytest.mark.parametrize("model", _MODELS)
async def test_adjustment_removes_the_fake_bonus_day_collapse(
    db_session: AsyncSession, model: type
) -> None:
    """The -50.3% print becomes a real ~-0.6% move on the adjusted series."""
    sec_id = await _seed(db_session)
    repo = SqlLegacyOHLCVRepository(db_session, model_cls=model)
    bars = [_bar(d, c) for d, c in sorted(_CLOSES.items())]
    await repo.upsert_bars(sec_id, bars)

    factors = compute_adjustment_factors([b.date for b in bars], [_BONUS])
    await repo.update_adjustment_factors(sec_id, factors)
    await db_session.commit()

    stored = await repo.bars_for_security(
        sec_id, start=date(2017, 9, 1), end=date(2017, 9, 30)
    )
    before, on_ex = stored[0], stored[1]

    # Raw prints still collapse by half; that is the archive's own number.
    raw_move = on_ex.close / before.close - 1
    assert raw_move < Decimal("-0.5")

    assert before.adj_close is not None
    assert on_ex.adj_close is not None
    adj_move = on_ex.adj_close / before.adj_close - 1
    assert abs(adj_move) < Decimal("0.01")


@pytest.mark.parametrize("model", _MODELS)
async def test_adjustment_matches_the_live_close_times_factor_invariant(
    db_session: AsyncSession, model: type
) -> None:
    """``adj_close == close * adj_factor``, the same invariant the live table holds."""
    sec_id = await _seed(db_session)
    repo = SqlLegacyOHLCVRepository(db_session, model_cls=model)
    bars = [_bar(d, c) for d, c in sorted(_CLOSES.items())]
    await repo.upsert_bars(sec_id, bars)
    await repo.update_adjustment_factors(
        sec_id, compute_adjustment_factors([b.date for b in bars], [_BONUS])
    )
    await db_session.commit()

    rows = (
        await db_session.execute(
            LegacyOHLCVDailyModel.__table__.select()
            if model is LegacyOHLCVDailyModel
            else BSELegacyOHLCVDailyModel.__table__.select()
        )
    ).all()
    assert rows
    for row in rows:
        assert row.adj_factor > 0
        assert row.adj_close == row.close * row.adj_factor


@pytest.mark.parametrize("model", _MODELS)
async def test_reingesting_a_bar_preserves_the_adjusted_close(
    db_session: AsyncSession, model: type
) -> None:
    """A re-run of the backfill must not wipe adj_close back to the raw print.

    Providers never report an adjusted close, so the upsert has to re-derive it
    from the stored ``adj_factor`` instead of writing the incoming ``None``.
    """
    sec_id = await _seed(db_session)
    repo = SqlLegacyOHLCVRepository(db_session, model_cls=model)
    bars = [_bar(d, c) for d, c in sorted(_CLOSES.items())]
    await repo.upsert_bars(sec_id, bars)
    await repo.update_adjustment_factors(
        sec_id, compute_adjustment_factors([b.date for b in bars], [_BONUS])
    )
    await db_session.commit()

    adjusted_before = [b.adj_close for b in await repo.bars_for_security(
        sec_id, start=date(2017, 9, 1), end=date(2017, 9, 30)
    )]

    # Re-ingest the identical raw bars, exactly as a backfill re-run would.
    await repo.upsert_bars(sec_id, bars)
    await db_session.commit()

    adjusted_after = [b.adj_close for b in await repo.bars_for_security(
        sec_id, start=date(2017, 9, 1), end=date(2017, 9, 30)
    )]
    assert adjusted_after == adjusted_before


@pytest.mark.parametrize("model", _MODELS)
async def test_bars_without_actions_keep_factor_one(
    db_session: AsyncSession, model: type
) -> None:
    """No corporate action means factor 1 and no silent price change."""
    sec_id = await _seed(db_session)
    repo = SqlLegacyOHLCVRepository(db_session, model_cls=model)
    bars = [_bar(d, c) for d, c in sorted(_CLOSES.items())]
    await repo.upsert_bars(sec_id, bars)
    await repo.update_adjustment_factors(
        sec_id, compute_adjustment_factors([b.date for b in bars], [])
    )
    await db_session.commit()

    for stored in await repo.bars_for_security(
        sec_id, start=date(2017, 9, 1), end=date(2017, 9, 30)
    ):
        assert stored.adj_close == stored.close
