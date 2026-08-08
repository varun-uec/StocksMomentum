"""Unit tests for the RP-012 historical-ISIN backfill use case (no network)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from momentum25.application.use_cases.research.historical_isin_backfill import (
    HistoricalIsinBackfill,
    IsinProbeTarget,
)
from momentum25.domain.ports.market_data import RawBar


class _FakeProvider:
    """Serves canned legacy (symbol+ISIN) snapshots and counts fetches."""

    def __init__(self, legacy: dict[date, list[RawBar]]) -> None:
        self._legacy = legacy
        self.fetched: list[date] = []

    async def fetch_eod_from_legacy_archive(self, for_date: date) -> list[RawBar]:
        self.fetched.append(for_date)
        return self._legacy.get(for_date, [])


class _FakeSecurityRepo:
    """Records the fill-only ISIN backfill mapping."""

    def __init__(self) -> None:
        self.written: dict[int, str] = {}

    async def backfill_isins(self, isin_by_security_id: dict[int, str]) -> int:
        self.written = dict(isin_by_security_id)
        return len(isin_by_security_id)


def _bar(symbol: str, d: date, isin: str | None) -> RawBar:
    return RawBar(
        symbol=symbol,
        date=d,
        open=Decimal("1"),
        high=Decimal("1"),
        low=Decimal("1"),
        close=Decimal("1"),
        volume=1,
        isin=isin,
        turnover_value=Decimal("1"),
        prev_close=Decimal("1"),
    )


@pytest.mark.asyncio
async def test_resolves_isin_off_primary_probe_date() -> None:
    """The ghost's ISIN is read from its own ticker on its last-trade date."""
    d = date(2021, 1, 12)
    provider = _FakeProvider({d: [_bar("ADANIGAS", d, "INE399L01023")]})
    repo = _FakeSecurityRepo()
    uc = HistoricalIsinBackfill(provider, repo)

    summary = await uc.execute([IsinProbeTarget(2605, "ADANIGAS", (d,))])

    assert summary.resolved == {2605: "INE399L01023"}
    assert repo.written == {2605: "INE399L01023"}
    assert summary.written == 1
    assert summary.archive_fetches == 1


@pytest.mark.asyncio
async def test_falls_back_to_next_candidate_when_primary_absent() -> None:
    """A target missing on its primary date is resolved on a fallback date."""
    d1, d2 = date(2021, 1, 12), date(2020, 6, 1)
    provider = _FakeProvider(
        {d1: [], d2: [_bar("OLDSYM", d2, "INE000000001")]}
    )
    repo = _FakeSecurityRepo()
    uc = HistoricalIsinBackfill(provider, repo)

    summary = await uc.execute([IsinProbeTarget(7, "OLDSYM", (d1, d2))])

    assert summary.resolved == {7: "INE000000001"}
    assert summary.unresolved == []


@pytest.mark.asyncio
async def test_each_distinct_date_fetched_once_across_targets() -> None:
    """Two targets sharing a probe date trigger a single archive fetch for it."""
    d = date(2021, 1, 12)
    provider = _FakeProvider(
        {d: [_bar("A", d, "INE0000000A1"), _bar("B", d, "INE0000000B1")]}
    )
    repo = _FakeSecurityRepo()
    uc = HistoricalIsinBackfill(provider, repo)

    summary = await uc.execute(
        [IsinProbeTarget(1, "A", (d,)), IsinProbeTarget(2, "B", (d,))]
    )

    assert summary.resolved == {1: "INE0000000A1", 2: "INE0000000B1"}
    assert provider.fetched == [d]


@pytest.mark.asyncio
async def test_undiscoverable_target_is_disclosed_not_fabricated() -> None:
    """A ticker the archive never serves stays unresolved; no ISIN invented."""
    d = date(2021, 1, 12)
    provider = _FakeProvider({d: [_bar("OTHER", d, "INE000000009")]})
    repo = _FakeSecurityRepo()
    uc = HistoricalIsinBackfill(provider, repo)

    summary = await uc.execute([IsinProbeTarget(99, "GHOST", (d,))])

    assert summary.resolved == {}
    assert summary.written == 0
    assert summary.unresolved == ["GHOST#99"]
    assert repo.written == {}
