"""Unit tests for the survivorship-bias fix in HistoricalScreeningUseCase (Objective 2).

Verifies that a historical replay excludes securities not yet listed as of
the target date -- the bug was that ``_evaluate_universe`` used
``security_repo.list_active()`` unconditionally, so a stock listed in 2026
could silently appear in a 2020 backtest. Also verifies the per-run
universe-membership audit trail is persisted for both eligible and
excluded securities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from momentum25.application.use_cases.research.historical_screening import (
    HistoricalScreeningUseCase,
)
from momentum25.domain.entities.security import Security
from momentum25.domain.entities.strategy import Strategy, StrategyConfig
from momentum25.domain.value_objects.indicators import IndicatorSet
from momentum25.domain.value_objects.results import StockScore, UniverseMembership
from momentum25.domain.value_objects.types import Symbol


class _FakeSecurityRepo:
    def __init__(self, securities: list[Security]) -> None:
        self._securities = securities

    async def list_active(self) -> list[Security]:
        return self._securities


class _FakeOHLCVRepo:
    async def get_series(self, security_id: int, lookback_days: int, as_of: date) -> Any:
        from momentum25.domain.entities.market_data import OHLCVBar, OHLCVSeries

        # A bar dated ``as_of`` keeps this fixture out of the (separately
        # tested) staleness exclusion -- this test isolates the listing_date
        # filter only.
        bar = OHLCVBar(
            date=as_of,
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            volume=1_000_000,
        )
        return OHLCVSeries(security_id=security_id, bars=(bar,))


class _FakeStrategyRepo:
    def __init__(self, strategy: Strategy) -> None:
        self._strategy = strategy

    async def get_active(self, name: str) -> Strategy | None:
        return self._strategy


class _FakeIndicatorPipeline:
    """Returns sufficient-history indicators for every symbol (sma200 set)."""

    async def compute(
        self, symbol: str, reference_date: date, config: dict[str, Any]
    ) -> IndicatorSet:
        return IndicatorSet(as_of=reference_date, sma200=Decimal("100"))


class _FakeStrategyEngine:
    def score_security(self, ctx: Any, strategy: Strategy) -> StockScore:
        return StockScore(
            security_id=ctx.security.id,
            momentum_score=Decimal("50"),
            buy_setup_score=Decimal("50"),
            engine_results=(),
            hard_filters_passed=True,
        )

    def rank(self, scores: list[StockScore], strategy: Strategy) -> list[Any]:
        from momentum25.domain.value_objects.results import Ranking

        return [
            Ranking(
                security_id=s.security_id,
                momentum_score=s.momentum_score,
                buy_setup_score=s.buy_setup_score,
                rank=i + 1,
            )
            for i, s in enumerate(scores)
        ]


@dataclass
class _FakeScreeningRunRepo:
    """Captures created runs and saved results/memberships for assertions."""

    next_id: int = 1
    saved_memberships: list[UniverseMembership] = field(default_factory=list)
    updated_runs: list[Any] = field(default_factory=list)

    async def create(self, run: Any) -> int:
        run_id = self.next_id
        self.next_id += 1
        return run_id

    async def update(self, run: Any) -> None:
        self.updated_runs.append(run)

    async def save_results(self, run_id: int, scores: list[Any], rankings: list[Any]) -> None:
        pass

    async def save_universe_membership(
        self, run_id: int, memberships: list[UniverseMembership]
    ) -> None:
        self.saved_memberships.extend(memberships)


def _strategy() -> Strategy:
    return Strategy(
        id=1,
        name="test_strategy",
        version=1,
        config=StrategyConfig(name="test_strategy", version=1, engines=()),
        config_hash="hash",
    )


@pytest.mark.asyncio
async def test_excludes_securities_not_yet_listed_as_of_historical_date() -> None:
    as_of_date = date(2020, 1, 1)
    securities = [
        Security(symbol=Symbol("OLD"), name="Old Co", id=1, listing_date=date(2015, 1, 1)),
        Security(symbol=Symbol("FUTURE"), name="Future Co", id=2, listing_date=date(2025, 1, 1)),
        Security(symbol=Symbol("UNKNOWN"), name="Unknown Listing", id=3, listing_date=None),
    ]
    run_repo = _FakeScreeningRunRepo()
    use_case = HistoricalScreeningUseCase(
        security_repo=_FakeSecurityRepo(securities),
        ohlcv_repo=_FakeOHLCVRepo(),
        screening_run_repo=run_repo,
        strategy_repo=_FakeStrategyRepo(_strategy()),
        indicator_pipeline=_FakeIndicatorPipeline(),
        strategy_engine=_FakeStrategyEngine(),
    )

    result = await use_case.execute("test_strategy", as_of_date)

    # Only OLD and UNKNOWN (no listing_date) should have been evaluated.
    assert result["total_evaluated"] == 2

    membership_by_id = {m.security_id: m for m in run_repo.saved_memberships}
    assert membership_by_id[1].eligible is True
    assert membership_by_id[2].eligible is False
    assert membership_by_id[2].reason == "not_yet_listed"
    assert membership_by_id[3].eligible is True

    # The residual survivorship-bias limitation must be disclosed, not hidden.
    stats = run_repo.updated_runs[-1].stats
    assert stats["excluded_not_yet_listed"] == 1
    assert "survivorship_bias_disclosure" in stats


class _PerSecurityOHLCVRepo:
    """Returns a caller-supplied latest bar date per security_id."""

    def __init__(self, latest_bar_by_security: dict[int, date | None]) -> None:
        self._latest_bar_by_security = latest_bar_by_security

    async def get_series(self, security_id: int, lookback_days: int, as_of: date) -> Any:
        from momentum25.domain.entities.market_data import OHLCVBar, OHLCVSeries

        latest = self._latest_bar_by_security.get(security_id)
        if latest is None:
            return OHLCVSeries(security_id=security_id, bars=())
        bar = OHLCVBar(
            date=latest,
            open=Decimal("100"),
            high=Decimal("101"),
            low=Decimal("99"),
            close=Decimal("100"),
            volume=1_000_000,
        )
        return OHLCVSeries(security_id=security_id, bars=(bar,))


@pytest.mark.asyncio
async def test_excludes_securities_with_stale_ohlcv_data() -> None:
    """A security whose latest bar is far older than as_of_date must be excluded.

    Regression test: previously any security in the active universe was
    scored using whatever bars existed on or before as_of_date, however old
    the most recent one was -- a security whose data ingestion stopped
    months or years earlier would still be evaluated (and could still rank)
    using a stale close as if it reflected the screening date.
    """
    as_of_date = date(2026, 6, 24)
    securities = [
        Security(symbol=Symbol("FRESH"), name="Fresh Co", id=1, listing_date=date(2015, 1, 1)),
        Security(symbol=Symbol("STALE"), name="Stale Co", id=2, listing_date=date(2015, 1, 1)),
        Security(symbol=Symbol("NODATA"), name="No Data Co", id=3, listing_date=date(2015, 1, 1)),
    ]
    run_repo = _FakeScreeningRunRepo()
    use_case = HistoricalScreeningUseCase(
        security_repo=_FakeSecurityRepo(securities),
        ohlcv_repo=_PerSecurityOHLCVRepo(
            {1: date(2026, 6, 20), 2: date(2024, 11, 13), 3: None}
        ),
        screening_run_repo=run_repo,
        strategy_repo=_FakeStrategyRepo(_strategy()),
        indicator_pipeline=_FakeIndicatorPipeline(),
        strategy_engine=_FakeStrategyEngine(),
    )

    await use_case.execute("test_strategy", as_of_date)

    membership_by_id = {m.security_id: m for m in run_repo.saved_memberships}
    assert membership_by_id[1].eligible is True
    assert membership_by_id[2].eligible is False
    assert membership_by_id[2].reason == "stale_data"
    assert membership_by_id[3].eligible is False
    assert membership_by_id[3].reason == "stale_data"

    stats = run_repo.updated_runs[-1].stats
    assert stats["excluded_stale_data"] == 2
