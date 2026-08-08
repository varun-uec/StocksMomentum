"""Phase 0.1 / 0.2 — declared-universe admission and the ingestion boundary.

Phase 0.1: the live screening path never applied the liquidity floor its own
strategy JSON declares (``config.universe``). Instead ``ExecuteScreening``
truncated an alphabetically-sorted symbol list to its first 500 entries under a
"Cap at Nifty 500 scope" comment. These tests pin the replacement: admission is
decided by the declared floor, per security, with an explainable reason.

Phase 0.2: ``ScreeningOrchestrator`` fetched EOD bars and discarded them without
persisting. These tests pin that the orchestrator no longer takes a market-data
provider at all and screens purely from persisted state.
"""

from __future__ import annotations

import inspect
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from momentum25.application.use_cases.screening import ExecuteScreening
from momentum25.application.use_cases.screening_orchestrator import ScreeningOrchestrator
from momentum25.domain.entities.market_data import OHLCVBar
from momentum25.domain.entities.strategy import EngineConfig, Strategy, StrategyConfig
from momentum25.domain.ports.market_data import RawBar, RawInstrument
from momentum25.domain.scoring.ranking_engine import RankingEngineImpl
from momentum25.domain.scoring.scoring_engine import ScoringEngineImpl
from momentum25.domain.strategy.engine_registry import EngineRegistry
from momentum25.domain.strategy.strategy_engine import StrategyEngine
from momentum25.infrastructure.persistence.models import SecurityModel
from momentum25.infrastructure.persistence.repositories import (
    SqlOHLCVRepository,
    SqlScreeningRunRepository,
    SqlSecurityRepository,
    SqlStrategyRepository,
)
from momentum25.infrastructure.pipelines.indicator_pipeline import (
    INDICATOR_VERSION,
    IndicatorPipelineImpl,
)

_START = date(2024, 1, 1)
_DAYS = 300
_TARGET = _START + timedelta(days=_DAYS - 1)


async def _seed_security(session: AsyncSession, symbol: str) -> SecurityModel:
    model = SecurityModel(symbol=symbol, name=symbol.title(), is_active=True)
    session.add(model)
    await session.flush()
    await session.refresh(model)
    return model


async def _seed_uptrend(
    session: AsyncSession,
    security_id: int,
    *,
    base_price: float = 100.0,
    turnover: Decimal | None | str = "auto",
    days: int = _DAYS,
) -> None:
    """Seed a rising series. ``turnover='auto'`` means realistic close x volume."""
    repo = SqlOHLCVRepository(session)
    bars = []
    price = base_price
    for i in range(days):
        close = Decimal(str(price + 1))
        volume = 1_000_000
        bars.append(
            OHLCVBar(
                date=_START + timedelta(days=i),
                open=Decimal(str(price)),
                high=Decimal(str(price + 2)),
                low=Decimal(str(price - 1)),
                close=close,
                volume=volume,
                turnover_value=(
                    close * Decimal(volume) if turnover == "auto" else turnover
                ),
            )
        )
        price += 0.5
    await repo.upsert_bars(security_id, bars)
    await session.commit()


async def _membership_reasons(session: AsyncSession) -> list[str]:
    """Return the persisted exclusion reasons for the most recent run.

    Read straight from ``universe_membership`` rather than through a repository:
    the repository is write-only for this table, and adding a read method used by
    nothing but a test would be dead production code.
    """
    from sqlalchemy import select

    from momentum25.infrastructure.persistence.models import UniverseMembershipModel

    rows = await session.execute(
        select(UniverseMembershipModel.reason)
        .where(UniverseMembershipModel.eligible.is_(False))
        .order_by(UniverseMembershipModel.security_id)
    )
    return [r for (r,) in rows.all()]


def _strategy(universe: dict | None = None) -> Strategy:
    # config_hash must vary with the config: screening_runs is uniquely keyed on
    # (strategy_id, run_date, data_version, config_hash), so two runs of different
    # universes on the same date would otherwise collide.
    return Strategy(
        name="test_strategy",
        version=1,
        config_hash=f"test-hash-{hash(repr(sorted((universe or {}).items()))) & 0xFFFF:04x}",
        config=StrategyConfig(
            name="test_strategy",
            version=1,
            engines=(EngineConfig(id="trend_template", enabled=True, weight=Decimal("1")),),
            universe=universe or {},
        ),
    )


def _orchestrator(
    session: AsyncSession, strategy: Strategy, *, indicators: dict | None = None
) -> ScreeningOrchestrator:
    from momentum25.domain.engines.trend_template import TrendTemplateEngine

    registry = EngineRegistry()
    registry.register(TrendTemplateEngine())
    return ScreeningOrchestrator(
        security_repo=SqlSecurityRepository(session),
        ohlcv_repo=SqlOHLCVRepository(session),
        screening_run_repo=SqlScreeningRunRepository(session),
        indicator_pipeline=IndicatorPipelineImpl(session),
        strategy_engine=StrategyEngine(
            engines=registry, scoring=ScoringEngineImpl(), ranking=RankingEngineImpl()
        ),
        strategy=strategy,
        strategy_repo=SqlStrategyRepository(session),
    )


# ── Phase 0.2: the orchestrator does not ingest ──────────────────────────────


def test_orchestrator_takes_no_market_data_provider() -> None:
    """The discarded-fetch parameter is gone from the constructor.

    Keeping an injected provider on a class that never fetches is exactly what
    let the no-op sync read as working code.
    """
    params = inspect.signature(ScreeningOrchestrator.__init__).parameters
    assert "market_data_provider" not in params


@pytest.mark.asyncio
async def test_orchestrator_screens_without_any_provider(db_session: AsyncSession) -> None:
    """A full run completes from persisted bars alone, with no network collaborator."""
    sec = await _seed_security(db_session, "LIQUID")
    await _seed_uptrend(db_session, sec.id)

    summary = await _orchestrator(db_session, _strategy()).run_daily_screening(_TARGET)

    assert summary.total_evaluated == 1
    assert summary.total_passed + summary.total_failed == 1
    assert summary.total_skipped_ineligible_universe == 0


@pytest.mark.asyncio
async def test_run_stats_record_indicator_version(db_session: AsyncSession) -> None:
    """Runs are stamped with the indicator-formula revision, not just config_hash.

    config_hash covers the strategy but not the formulas, so without this stamp a
    run computed with the pre-Phase-0 RSI/ATR is indistinguishable from one
    computed with the corrected formulas.
    """
    sec = await _seed_security(db_session, "LIQUID")
    await _seed_uptrend(db_session, sec.id)

    await _orchestrator(db_session, _strategy()).run_daily_screening(_TARGET)

    runs, _ = await SqlScreeningRunRepository(db_session).list_runs("completed", 1, 0)
    assert runs[0].stats["indicator_version"] == INDICATOR_VERSION
    assert runs[0].stats["universe_source"] == "declared_liquidity_floor"


# ── Phase 0.1: the declared floor decides admission ──────────────────────────


@pytest.mark.asyncio
async def test_security_below_turnover_floor_is_excluded_with_reason(
    db_session: AsyncSession,
) -> None:
    """A thinly-traded name is excluded from scoring and says why.

    Turnover of Rs 1,000/day is four orders of magnitude below the declared
    Rs 10,000,000 floor.
    """
    sec = await _seed_security(db_session, "ILLIQUID")
    await _seed_uptrend(db_session, sec.id, turnover=Decimal("1000"))

    strategy = _strategy({"min_avg_turnover_inr": 10_000_000, "min_price_inr": 20})
    summary = await _orchestrator(db_session, strategy).run_daily_screening(_TARGET)

    assert summary.total_skipped_ineligible_universe == 1
    assert summary.total_passed == 0, "an excluded security must never be scored"

    assert await _membership_reasons(db_session) == ["below_liquidity_floor"]


@pytest.mark.asyncio
async def test_security_below_price_floor_is_excluded_with_reason(
    db_session: AsyncSession,
) -> None:
    """A penny stock is excluded on price even when its turnover is ample."""
    sec = await _seed_security(db_session, "PENNY")
    # Starts at 1.0 and rises 0.5/day, but volume keeps turnover far above the floor.
    await _seed_uptrend(db_session, sec.id, base_price=1.0, turnover=Decimal("50000000"))

    strategy = _strategy({"min_price_inr": 500, "min_avg_turnover_inr": 10_000_000})
    summary = await _orchestrator(db_session, strategy).run_daily_screening(_TARGET)

    assert summary.total_skipped_ineligible_universe == 1
    assert await _membership_reasons(db_session) == ["close_below_floor"]


@pytest.mark.asyncio
async def test_missing_turnover_excludes_rather_than_estimates(
    db_session: AsyncSession,
) -> None:
    """No real turnover means exclusion with a disclosed reason, never an estimate.

    The pre-Phase-0 ``fetch_eod`` path dropped the turnover column entirely, so
    this is the state every ingested bar was in. Substituting
    ``avg_volume50 x close`` here would silently admit securities on a guessed
    liquidity figure.
    """
    sec = await _seed_security(db_session, "NOTURNOVER")
    await _seed_uptrend(db_session, sec.id, turnover=None)

    strategy = _strategy({"min_avg_turnover_inr": 10_000_000, "min_price_inr": 20})
    summary = await _orchestrator(db_session, strategy).run_daily_screening(_TARGET)

    assert summary.total_skipped_ineligible_universe == 1
    assert await _membership_reasons(db_session) == ["insufficient_turnover_data"]


@pytest.mark.asyncio
async def test_declared_thresholds_are_honoured_not_hardcoded(
    db_session: AsyncSession,
) -> None:
    """The same security is admitted or rejected purely by its strategy config.

    Proves the floor is read from ``config.universe`` (ADR-005) rather than from
    the research module's fixed constants.
    """
    sec = await _seed_security(db_session, "MIDLIQUID")
    # close ~250 x 1,000,000 shares => turnover ~250,000,000
    await _seed_uptrend(db_session, sec.id, base_price=200.0)

    permissive = await _orchestrator(
        db_session, _strategy({"min_avg_turnover_inr": 10_000_000})
    ).run_daily_screening(_TARGET)
    assert permissive.total_skipped_ineligible_universe == 0

    strict = await _orchestrator(
        db_session, _strategy({"min_avg_turnover_inr": 10_000_000_000})
    ).run_daily_screening(_TARGET)
    assert strict.total_skipped_ineligible_universe == 1


# ── Phase 0.1: no alphabetical truncation during ingestion ───────────────────


class _FakeProvider:
    """A provider serving a wide, deliberately alphabetical symbol universe."""

    def __init__(self, symbol_count: int) -> None:
        # ZZZ.. sorts last, so anything relying on the old symbols[:500] slice
        # drops every one of these.
        self.symbols = [f"SYM{i:04d}" for i in range(symbol_count)]
        self.fetch_eod_calls = 0
        self.fetch_eod_full_calls = 0

    async def fetch_eod(self, for_date: date) -> list[RawBar]:
        self.fetch_eod_calls += 1
        return self._bars(for_date, with_turnover=False)

    async def fetch_eod_full(self, for_date: date) -> list[RawBar]:
        self.fetch_eod_full_calls += 1
        return self._bars(for_date, with_turnover=True)

    def _bars(self, for_date: date, *, with_turnover: bool) -> list[RawBar]:
        # Returns bars for any requested session date, not just _TARGET: since
        # _fetch_eod_range now walks real trading sessions (Phase 1.6) rather
        # than every calendar day, a fixture gated on one exact date (which
        # may itself be a non-session) would starve the caller entirely.
        return [
            RawBar(
                symbol=s,
                date=for_date,
                open=Decimal("100"),
                high=Decimal("102"),
                low=Decimal("99"),
                close=Decimal("101"),
                volume=1_000_000,
                turnover_value=Decimal("101000000") if with_turnover else None,
            )
            for s in self.symbols
        ]

    async def fetch_instrument_master(self) -> list[RawInstrument]:
        return [RawInstrument(symbol=s, name=s) for s in self.symbols]


@pytest.mark.asyncio
async def test_ingestion_does_not_truncate_universe_alphabetically(
    db_session: AsyncSession,
) -> None:
    """All 600 traded symbols are ingested, not the first 500 by name.

    This is the direct regression test for the "Cap at Nifty 500 scope" slice:
    under the old code SYM0500..SYM0599 were silently dropped from every run.
    """
    provider = _FakeProvider(600)
    security_repo = SqlSecurityRepository(db_session)

    use_case = ExecuteScreening(
        market_data_provider=provider,
        security_repo=security_repo,
        ohlcv_repo=SqlOHLCVRepository(db_session),
        screening_run_repo=SqlScreeningRunRepository(db_session),
        indicator_pipeline=IndicatorPipelineImpl(db_session),
        strategy_engine=None,
    )

    # _fetch_eod_range now walks real trading sessions (Phase 1.6), so a
    # single-day range must actually contain one; _TARGET alone can land on
    # a weekend (it does here). A 7-day lookback guarantees a session.
    symbols = sorted(
        {b.symbol for b in await use_case._fetch_eod_range(_TARGET - timedelta(days=7), _TARGET)}
    )
    securities = await use_case._upsert_securities(symbols)

    assert len(securities) == 600
    stored = {str(s.symbol) for s in await security_repo.list_active()}
    assert "SYM0599" in stored, "last-by-name symbol must survive ingestion"
    assert "SYM0500" in stored


@pytest.mark.asyncio
async def test_ingestion_uses_the_turnover_carrying_fetch(db_session: AsyncSession) -> None:
    """Ingestion must call fetch_eod_full; plain fetch_eod drops turnover.

    Without real turnover the declared liquidity floor is incomputable and every
    security resolves to ``insufficient_turnover_data`` — an empty universe.
    """
    provider = _FakeProvider(3)
    use_case = ExecuteScreening(
        market_data_provider=provider,
        security_repo=SqlSecurityRepository(db_session),
        ohlcv_repo=SqlOHLCVRepository(db_session),
        screening_run_repo=SqlScreeningRunRepository(db_session),
        indicator_pipeline=IndicatorPipelineImpl(db_session),
        strategy_engine=None,
    )

    # See the comment on the sibling test above: _fetch_eod_range now walks
    # real sessions, so the range must actually contain one.
    bars = await use_case._fetch_eod_range(_TARGET - timedelta(days=7), _TARGET)

    assert provider.fetch_eod_full_calls > 0
    assert provider.fetch_eod_calls == 0
    assert all(b.turnover_value is not None for b in bars)


# ── Cross-version comparisons are disclosed, never silent ────────────────────


@pytest.mark.asyncio
async def test_comparing_runs_of_different_indicator_versions_is_disclosed(
    db_session: AsyncSession,
) -> None:
    """A diff across indicator versions must flag itself as not like-for-like.

    config_hash covers the strategy but not the RSI/ATR formulas, so without this
    disclosure the score deltas caused by the Phase 0.3/0.4 correction would be
    silently attributed to whatever change the diff was investigating.
    """
    from momentum25.application.use_cases.research.validation import (
        ValidateRunComparisonUseCase,
    )

    sec = await _seed_security(db_session, "LIQUID")
    await _seed_uptrend(db_session, sec.id)

    run_repo = SqlScreeningRunRepository(db_session)
    await _orchestrator(db_session, _strategy()).run_daily_screening(_TARGET)
    await _orchestrator(db_session, _strategy({"min_price_inr": 5})).run_daily_screening(
        _TARGET
    )
    runs, _ = await run_repo.list_runs("completed", 2, 0)
    newer, older = runs[0], runs[1]

    # Restamp one run as if it had been produced by the pre-correction formulas.
    stale = dict(older.stats or {})
    stale["indicator_version"] = 1
    older.stats = stale
    await run_repo.update(older)
    await db_session.commit()

    report = await ValidateRunComparisonUseCase(run_repo).execute(older.id, newer.id)

    assert report.indicator_version_a == 1
    assert report.indicator_version_b == INDICATOR_VERSION
    assert report.indicator_versions_differ() is True


@pytest.mark.asyncio
async def test_same_version_comparison_is_not_flagged(db_session: AsyncSession) -> None:
    """Two runs from the same formulas compare cleanly, with no false alarm."""
    from momentum25.application.use_cases.research.validation import (
        ValidateRunComparisonUseCase,
    )

    sec = await _seed_security(db_session, "LIQUID")
    await _seed_uptrend(db_session, sec.id)

    run_repo = SqlScreeningRunRepository(db_session)
    await _orchestrator(db_session, _strategy()).run_daily_screening(_TARGET)
    await _orchestrator(db_session, _strategy({"min_price_inr": 5})).run_daily_screening(
        _TARGET
    )
    runs, _ = await run_repo.list_runs("completed", 2, 0)

    report = await ValidateRunComparisonUseCase(run_repo).execute(runs[1].id, runs[0].id)

    assert report.indicator_versions_differ() is False
