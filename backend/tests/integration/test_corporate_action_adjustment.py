"""Phase 0.5 — corporate-action adjustment, end to end.

The adjustment machinery (parser, factor computation, repository write) all
existed and was unit-tested, but nothing invoked it: every bar's ``adj_factor``
stayed 1, so a split or bonus left a raw price discontinuity in the series that
long-window indicators silently treated as a real price move.

These tests cover the parts that were never verified:

* the factor actually reaches the indicator pipeline and changes SMA/RSI/ATR;
* ``adj_close`` survives re-ingestion of an already-adjusted bar;
* an unparseable action is disclosed rather than guessed at.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.application.services.corporate_actions import refresh_adjustment_factors
from momentum25.domain.entities.market_data import OHLCVBar, compute_adjustment_factors
from momentum25.domain.ports.market_data import RawCorporateAction
from momentum25.infrastructure.persistence.models import OHLCVDailyModel, SecurityModel
from momentum25.infrastructure.persistence.repositories import (
    SqlOHLCVRepository,
    SqlSecurityRepository,
)
from momentum25.infrastructure.persistence.repositories.corporate_actions import (
    SqlCorporateActionRepository,
)
from momentum25.infrastructure.pipelines.indicator_pipeline import IndicatorPipelineImpl
from momentum25.infrastructure.providers.bhavcopy import _parse_corporate_action_ratio

_START = date(2024, 1, 1)
_DAYS = 300
_TARGET = _START + timedelta(days=_DAYS - 1)
_EX_DATE = _START + timedelta(days=250)


class _StubProvider:
    """Serves a fixed corporate-action list; performs no network I/O."""

    def __init__(self, actions: list[RawCorporateAction]) -> None:
        self._actions = actions

    async def fetch_corporate_actions(
        self, symbol: str, since: date
    ) -> list[RawCorporateAction]:
        return [a for a in self._actions if a.ex_date >= since]


async def _seed(
    session: AsyncSession, symbol: str = "SPLITCO", ex_date: date = _EX_DATE
) -> int:
    """Seed a security whose raw close halves at a 1:1 bonus ex-date.

    A 1:1 bonus doubles the share count, so the quoted price halves: the stock
    trades at 200 before ``ex_date`` and at 100 from ``ex_date`` on. Nothing
    economically happened — a holder's position is worth the same on both sides.
    Applying the 0.5 backward factor to the pre-ex bars therefore has an exactly
    known answer: a perfectly flat adjusted series at 100.
    """
    security = SecurityModel(symbol=symbol, name=symbol.title(), is_active=True)
    session.add(security)
    await session.flush()
    await session.refresh(security)

    repo = SqlOHLCVRepository(session)
    bars = []
    for i in range(_DAYS):
        d = _START + timedelta(days=i)
        price = Decimal("200") if d < ex_date else Decimal("100")
        bars.append(
            OHLCVBar(
                date=d,
                open=price,
                high=price + Decimal("2"),
                low=price - Decimal("1"),
                close=price,
                volume=1_000_000,
                turnover_value=price * Decimal("1000000"),
            )
        )
    await repo.upsert_bars(security.id, bars)
    await session.commit()
    return int(security.id)


# ── The factor reaches the indicators ────────────────────────────────────────


@pytest.mark.asyncio
async def test_adjustment_changes_computed_indicators(db_session: AsyncSession) -> None:
    """Indicators must differ before and after the adjustment is applied.

    A 1:1 bonus scales every pre-ex-date price by 1/2. Unadjusted, the SMA200
    window straddles a fabricated 200->100 halving; adjusted, the series is flat
    at 100, so the SMA200 must move from 175 to exactly 100.
    """
    security_id = await _seed(db_session)
    pipeline = IndicatorPipelineImpl(db_session)

    before = await pipeline.compute("SPLITCO", _TARGET, {})
    assert before.sma200 is not None

    updated = await refresh_adjustment_factors(
        market_data_provider=_StubProvider(
            [
                RawCorporateAction(
                    symbol="SPLITCO",
                    ex_date=_EX_DATE,
                    action_type="bonus",
                    ratio=Decimal("0.5"),
                    raw_subject="Bonus 1:1",
                )
            ]
        ),
        corporate_action_repo=SqlCorporateActionRepository(db_session),
        ohlcv_repo=SqlOHLCVRepository(db_session),
        symbol="SPLITCO",
        security_id=security_id,
        as_of=_TARGET,
    )
    await db_session.commit()
    assert updated > 0, "the refresh must write factors for the seeded bars"

    after = await pipeline.compute("SPLITCO", _TARGET, {})
    assert after.sma200 is not None
    assert after.sma200 != before.sma200, (
        "adj_factor must reach the indicator pipeline; equal SMAs mean the "
        "adjustment was computed and then ignored"
    )

    # Adjusted, the whole series is a flat 100 (pre-ex 200 x 0.5, post-ex 100),
    # so the SMA200 is exactly 100 -- the split has been fully neutralised.
    assert after.sma200 == pytest.approx(Decimal("100"), abs=Decimal("0.01"))

    # Unadjusted, the SMA200 window still contains 150 raw 200s and 50 raw 100s:
    # (150 x 200 + 50 x 100) / 200 = 175. That 75-point error is the defect.
    assert before.sma200 == pytest.approx(Decimal("175"), abs=Decimal("0.01"))


@pytest.mark.asyncio
async def test_adjustment_removes_the_artificial_volatility_spike(
    db_session: AsyncSession,
) -> None:
    """ATR must fall once the fabricated price gap is adjusted away.

    Unadjusted, the ex-date bar shows a 100-point true range against the prior
    close. That is the exact failure mode that would fire a stop-loss in Phase 3
    on a split that never moved the stock.
    """
    # The ex-date sits 5 sessions from the end so the gap is inside the 14-bar
    # ATR window, while the series still carries the 277 bars the pipeline needs.
    late_ex_date = _TARGET - timedelta(days=5)
    security_id = await _seed(db_session, ex_date=late_ex_date)
    pipeline = IndicatorPipelineImpl(db_session)

    as_of = _TARGET
    before = await pipeline.compute("SPLITCO", as_of, {})

    await refresh_adjustment_factors(
        market_data_provider=_StubProvider(
            [
                RawCorporateAction(
                    symbol="SPLITCO",
                    ex_date=late_ex_date,
                    action_type="bonus",
                    ratio=Decimal("0.5"),
                    raw_subject="Bonus 1:1",
                )
            ]
        ),
        corporate_action_repo=SqlCorporateActionRepository(db_session),
        ohlcv_repo=SqlOHLCVRepository(db_session),
        symbol="SPLITCO",
        security_id=security_id,
        as_of=as_of,
    )
    await db_session.commit()
    after = await pipeline.compute("SPLITCO", as_of, {})

    assert before.atr14 is not None and after.atr14 is not None
    assert after.atr14 < before.atr14, "adjusting must remove the fabricated gap"


# ── adj_close survives re-ingestion ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_reingestion_preserves_adjusted_close(db_session: AsyncSession) -> None:
    """Re-upserting a bar must not desync adj_close from adj_factor.

    Providers never report an adjusted close, so an ingested bar carries
    ``adj_close=None``. Writing that straight through wiped the adjusted close
    while leaving ``adj_factor`` set — and forward-return research reads
    ``adj_close`` while the indicator pipeline reads ``adj_factor``, so the two
    silently disagreed about the same split.
    """
    security_id = await _seed(db_session)
    repo = SqlOHLCVRepository(db_session)

    factors = {_START + timedelta(days=i): Decimal("0.5") for i in range(200)}
    await repo.update_adjustment_factors(security_id, factors)
    await db_session.commit()

    async def _row(day: date) -> tuple[Decimal, Decimal, Decimal]:
        result = await db_session.execute(
            select(
                OHLCVDailyModel.close,
                OHLCVDailyModel.adj_close,
                OHLCVDailyModel.adj_factor,
            ).where(
                OHLCVDailyModel.security_id == security_id,
                OHLCVDailyModel.date == day,
            )
        )
        return result.one()

    day = _START + timedelta(days=10)
    close, adj_close, adj_factor = await _row(day)
    assert adj_factor == Decimal("0.5")
    assert adj_close == close * Decimal("0.5")

    # Re-ingest the very same raw bar, exactly as a repeated daily sync would.
    await repo.upsert_bars(
        security_id,
        [
            OHLCVBar(
                date=day,
                open=close,
                high=close + Decimal("2"),
                low=close - Decimal("1"),
                close=close,
                volume=1_000_000,
                turnover_value=close * Decimal("1000000"),
            )
        ],
    )
    await db_session.commit()

    close_after, adj_close_after, adj_factor_after = await _row(day)
    assert adj_factor_after == Decimal("0.5"), "factor must be preserved"
    assert adj_close_after is not None, "re-ingestion must not null the adjusted close"
    assert adj_close_after == close_after * adj_factor_after, (
        "invariant adj_close == close * adj_factor must hold after any ingestion"
    )


# ── Unparseable actions are disclosed, never guessed ─────────────────────────


def test_bonus_and_split_ratios_are_parsed() -> None:
    """The two recognized NSE subject formats yield correct multipliers."""
    # Bonus 1:1 -> holder ends with 2 shares for every 1; prior prices x 1/2.
    assert _parse_corporate_action_ratio("Bonus 1:1") == ("bonus", Decimal("1") / Decimal("2"))
    # Bonus 2:1 -> 3 shares for every 1; prior prices x 1/3.
    assert _parse_corporate_action_ratio("Bonus 2:1") == ("bonus", Decimal("1") / Decimal("3"))
    # Face value split 10 -> 2 is a 5:1 split; prior prices x 2/10.
    action_type, ratio = _parse_corporate_action_ratio(
        "Face Value Split From Rs 10 To Rs 2"
    )
    assert action_type == "split"
    assert ratio == Decimal("2") / Decimal("10")


def test_unrecognized_action_yields_no_ratio() -> None:
    """A dividend must not be turned into a price adjustment."""
    assert _parse_corporate_action_ratio("Interim Dividend Rs 5 Per Share") == (
        "other",
        None,
    )


def test_ratioless_actions_never_adjust_prices() -> None:
    """Actions with ratio=None leave every factor at 1.

    Guessing a ratio would silently corrupt every earlier bar — worse than a
    disclosed gap.
    """
    dates = [_START + timedelta(days=i) for i in range(5)]
    factors = compute_adjustment_factors(
        dates,
        [
            RawCorporateAction(
                symbol="X",
                ex_date=dates[3],
                action_type="other",
                ratio=None,
                raw_subject="Interim Dividend",
            )
        ],
    )
    assert set(factors.values()) == {Decimal("1")}


@pytest.mark.asyncio
async def test_refresh_is_idempotent(db_session: AsyncSession) -> None:
    """Running the refresh twice yields identical factors (determinism, ADR-009)."""
    security_id = await _seed(db_session)
    provider = _StubProvider(
        [
            RawCorporateAction(
                symbol="SPLITCO",
                ex_date=_EX_DATE,
                action_type="bonus",
                ratio=Decimal("0.5"),
                raw_subject="Bonus 1:1",
            )
        ]
    )

    async def _run() -> list[tuple[date, Decimal]]:
        await refresh_adjustment_factors(
            market_data_provider=provider,
            corporate_action_repo=SqlCorporateActionRepository(db_session),
            ohlcv_repo=SqlOHLCVRepository(db_session),
            symbol="SPLITCO",
            security_id=security_id,
            as_of=_TARGET,
        )
        await db_session.commit()
        rows = await db_session.execute(
            select(OHLCVDailyModel.date, OHLCVDailyModel.adj_factor)
            .where(OHLCVDailyModel.security_id == security_id)
            .order_by(OHLCVDailyModel.date)
        )
        return [(d, f) for d, f in rows.all()]

    assert await _run() == await _run()


@pytest.mark.asyncio
async def test_securities_without_actions_keep_factor_one(
    db_session: AsyncSession,
) -> None:
    """A security with no corporate actions is left completely untouched."""
    security_id = await _seed(db_session, "NOACTION")

    updated = await refresh_adjustment_factors(
        market_data_provider=_StubProvider([]),
        corporate_action_repo=SqlCorporateActionRepository(db_session),
        ohlcv_repo=SqlOHLCVRepository(db_session),
        symbol="NOACTION",
        security_id=security_id,
        as_of=_TARGET,
    )
    await db_session.commit()

    assert updated == 0
    rows = await db_session.execute(
        select(OHLCVDailyModel.adj_factor).where(
            OHLCVDailyModel.security_id == security_id
        )
    )
    assert {f for (f,) in rows.all()} == {Decimal("1")}


@pytest.mark.asyncio
async def test_active_universe_refresh_is_reachable_from_the_api_layer(
    db_session: AsyncSession,
) -> None:
    """The use case wired behind POST /research/corporate-actions/refresh works.

    Before Phase 0.5 this use case had a dependency provider but no endpoint, so
    nothing in a deployed system could ever populate an adjustment factor.
    """
    from momentum25.application.use_cases.research.refresh_corporate_actions import (
        RefreshCorporateActions,
    )

    await _seed(db_session, "SPLITCO")
    use_case = RefreshCorporateActions(
        market_data_provider=_StubProvider(
            [
                RawCorporateAction(
                    symbol="SPLITCO",
                    ex_date=_EX_DATE,
                    action_type="bonus",
                    ratio=Decimal("0.5"),
                    raw_subject="Bonus 1:1",
                )
            ]
        ),
        security_repo=SqlSecurityRepository(db_session),
        corporate_action_repo=SqlCorporateActionRepository(db_session),
        ohlcv_repo=SqlOHLCVRepository(db_session),
    )

    summary = await use_case.execute(_TARGET)

    assert summary["securities_processed"] == 1
    assert summary["bars_updated"] > 0
    assert summary["errors"] == 0
