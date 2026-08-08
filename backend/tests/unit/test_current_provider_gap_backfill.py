"""Unit tests for the RP-012 current-provider gap backfill use case (no network)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from momentum25.application.use_cases.research.current_provider_gap_backfill import (
    CurrentProviderGapBackfill,
)
from momentum25.domain.ports.market_data import RawBar


class _FakeProvider:
    """Serves canned legacy (ISIN+symbol) and current (symbol->price) snapshots."""

    def __init__(
        self,
        legacy: dict[date, list[RawBar]],
        current: dict[date, list[RawBar]],
    ) -> None:
        self._legacy = legacy
        self._current = current

    async def fetch_eod_from_legacy_archive(self, for_date: date) -> list[RawBar]:
        return self._legacy.get(for_date, [])

    async def fetch_eod_full(self, for_date: date) -> list[RawBar]:
        return self._current.get(for_date, [])


class _FakeOHLCVRepo:
    """Records upserts keyed by (security_id, date)."""

    def __init__(self) -> None:
        self.written: dict[tuple[int, date], RawBar] = {}

    async def upsert_bars(self, security_id: int, bars: list[object]) -> int:
        for b in bars:
            self.written[(security_id, b.date)] = b  # type: ignore[attr-defined]
        return len(bars)


def _bar(symbol: str, d: date, close: str, isin: str | None = None) -> RawBar:
    return RawBar(
        symbol=symbol,
        date=d,
        open=Decimal(close),
        high=Decimal(close),
        low=Decimal(close),
        close=Decimal(close),
        volume=100,
        isin=isin,
        turnover_value=Decimal("1000"),
        prev_close=Decimal(close),
    )


@pytest.mark.asyncio
async def test_resolves_old_ticker_via_isin_and_writes_current_price() -> None:
    """A renamed security's in-window bar is written from the current provider.

    Legacy prints the old ticker OLDSYM (with ISIN); the current snapshot serves
    OLDSYM's price. The security_id comes from the ISIN target map.
    """
    d1, d2 = date(2020, 1, 1), date(2020, 1, 2)
    legacy = {
        d1: [_bar("OLDSYM", d1, "10", isin="INE000000001")],
        d2: [_bar("OLDSYM", d2, "11", isin="INE000000001")],
    }
    current = {
        d1: [_bar("OLDSYM", d1, "10"), _bar("OTHER", d1, "99")],
        d2: [_bar("OLDSYM", d2, "11")],
    }
    repo = _FakeOHLCVRepo()
    uc = CurrentProviderGapBackfill(_FakeProvider(legacy, current), repo)

    summary = await uc.execute({42: "INE000000001"}, d1, d2)

    assert summary.rows_written == 2
    assert summary.securities_written == {42}
    assert repo.written[(42, d1)].close == Decimal("10")
    assert repo.written[(42, d2)].close == Decimal("11")
    assert summary.missing_from_current == 0


@pytest.mark.asyncio
async def test_missing_from_current_is_disclosed_not_fabricated() -> None:
    """When the current provider lacks the ticker, nothing is written; a miss is logged."""
    d1 = date(2020, 1, 1)
    legacy = {d1: [_bar("DEADSYM", d1, "10", isin="INE000000002")]}
    current = {d1: [_bar("OTHER", d1, "99")]}  # DEADSYM absent
    repo = _FakeOHLCVRepo()
    uc = CurrentProviderGapBackfill(_FakeProvider(legacy, current), repo)

    summary = await uc.execute({7: "INE000000002"}, d1, d1)

    assert summary.rows_written == 0
    assert summary.missing_from_current == 1
    assert repo.written == {}


@pytest.mark.asyncio
async def test_skip_existing_leaves_present_rows_untouched() -> None:
    """A partial-gap security only has its missing date filled; present date is skipped.

    The security already holds d1 in ohlcv_daily (passed via ``skip_existing``);
    only the missing d2 is written, so no existing production row is overwritten.
    """
    d1, d2 = date(2020, 1, 1), date(2020, 1, 2)
    legacy = {
        d1: [_bar("OLDSYM", d1, "10", isin="INE000000004")],
        d2: [_bar("OLDSYM", d2, "11", isin="INE000000004")],
    }
    current = {
        d1: [_bar("OLDSYM", d1, "10")],
        d2: [_bar("OLDSYM", d2, "11")],
    }
    repo = _FakeOHLCVRepo()
    uc = CurrentProviderGapBackfill(_FakeProvider(legacy, current), repo)

    summary = await uc.execute(
        {5: "INE000000004"}, d1, d2, skip_existing={5: {d1}}
    )

    assert summary.rows_written == 1
    assert summary.already_present_skipped == 1
    assert (5, d2) in repo.written
    assert (5, d1) not in repo.written


@pytest.mark.asyncio
async def test_non_target_isins_are_ignored() -> None:
    """Only target ISINs are written; other legacy rows are skipped."""
    d1 = date(2020, 1, 1)
    legacy = {d1: [_bar("OLDSYM", d1, "10", isin="INE000000003")]}
    current = {d1: [_bar("OLDSYM", d1, "10")]}
    repo = _FakeOHLCVRepo()
    uc = CurrentProviderGapBackfill(_FakeProvider(legacy, current), repo)

    summary = await uc.execute({99: "INE999999999"}, d1, d1)

    assert summary.rows_written == 0
    assert repo.written == {}
