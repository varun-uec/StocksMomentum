"""RefreshLatestMarketData tests — mapping, per-exchange isolation, session choice."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from momentum25.application.use_cases.market_data import RefreshLatestMarketData
from momentum25.domain.entities.market_data import OHLCVBar
from momentum25.domain.entities.security import Security
from momentum25.domain.ports.market_data import RawBar
from momentum25.domain.value_objects.types import Symbol

_MONDAY = date(2026, 8, 17)
_FRIDAY = date(2026, 8, 14)


class FakeClock:
    """A clock pinned to one date."""

    def __init__(self, today: date) -> None:
        self._today = today

    def today(self) -> date:
        return self._today

    def now(self) -> datetime:
        return datetime(self._today.year, self._today.month, self._today.day)


class FakeCalendar:
    """Weekday-only calendar — no exchange_calendars dependency in a unit test."""

    def is_session(self, day: date) -> bool:
        return day.weekday() < 5

    def sessions_between(self, start: date, end: date) -> list[date]:
        days = []
        current = start
        while current <= end:
            if self.is_session(current):
                days.append(current)
            current = date.fromordinal(current.toordinal() + 1)
        return days

    def next_session(self, after: date) -> date:
        current = date.fromordinal(after.toordinal() + 1)
        while not self.is_session(current):
            current = date.fromordinal(current.toordinal() + 1)
        return current


class FakeOHLCVRepository:
    """In-memory upsert with the same last-write-wins semantics as ON CONFLICT."""

    def __init__(self) -> None:
        self.bars: dict[tuple[int, date], OHLCVBar] = {}

    async def upsert_bars_batch(self, bars_by_security: dict[int, list[OHLCVBar]]) -> int:
        written = 0
        for security_id, bars in bars_by_security.items():
            for bar in bars:
                self.bars[(security_id, bar.date)] = bar
                written += 1
        return written


class FakeSecurityRepository:
    """Only the one method the use case depends on."""

    def __init__(self, securities: list[Security]) -> None:
        self._securities = securities

    async def list_active(self) -> list[Security]:
        return self._securities


class FakeProvider:
    """Returns a fixed bar list, or raises a fixed error."""

    def __init__(self, bars: list[RawBar] | None = None, error: Exception | None = None) -> None:
        self._bars = bars or []
        self._error = error
        self.calls: list[date] = []

    async def fetch_eod(self, for_date: date) -> list[RawBar]:
        self.calls.append(for_date)
        if self._error is not None:
            raise self._error
        return [b for b in self._bars if b.date == for_date]


def _security(security_id: int, symbol: str, exchange: str = "NSE") -> Security:
    return Security(
        id=security_id,
        symbol=Symbol(symbol),
        name=symbol,
        isin=None,
        exchange=exchange,
        is_active=True,
    )


def _raw(symbol: str, on: date = _FRIDAY) -> RawBar:
    return RawBar(
        symbol=symbol,
        date=on,
        open=Decimal("100"),
        high=Decimal("110"),
        low=Decimal("99"),
        close=Decimal("105"),
        volume=1000,
        prev_close=Decimal("98"),
        turnover_value=Decimal("105000"),
    )


def _use_case(
    providers: dict[str, FakeProvider],
    securities: list[Security],
    ohlcv_repo: FakeOHLCVRepository,
    today: date = _MONDAY,
) -> RefreshLatestMarketData:
    return RefreshLatestMarketData(
        providers=providers,  # type: ignore[arg-type]
        security_repo=FakeSecurityRepository(securities),  # type: ignore[arg-type]
        ohlcv_repo=ohlcv_repo,  # type: ignore[arg-type]
        calendar=FakeCalendar(),
        clock=FakeClock(today),
    )


@pytest.mark.asyncio
async def test_target_date_is_the_prior_friday_on_a_monday() -> None:
    """The latest completed session on a Monday is the preceding Friday."""
    provider = FakeProvider([_raw("INFY")])
    repo = FakeOHLCVRepository()
    use_case = _use_case({"NSE": provider}, [_security(1, "INFY")], repo)

    summary = await use_case.execute(["NSE"])

    assert summary.target_date == _FRIDAY
    assert provider.calls == [_FRIDAY]


@pytest.mark.asyncio
async def test_matched_symbol_is_upserted() -> None:
    """A bar whose symbol maps to an active security is written under that id."""
    repo = FakeOHLCVRepository()
    use_case = _use_case({"NSE": FakeProvider([_raw("INFY")])}, [_security(7, "INFY")], repo)

    summary = await use_case.execute(["NSE"])
    result = summary.results[0]

    assert result.securities_matched == 1
    assert result.rows_written == 1
    assert repo.bars[(7, _FRIDAY)].close == Decimal("105")
    assert repo.bars[(7, _FRIDAY)].turnover_value == Decimal("105000")
    assert summary.overall_status == "success"


@pytest.mark.asyncio
async def test_repeat_refresh_is_idempotent() -> None:
    """Running the same refresh twice leaves one bar per (security, date)."""
    repo = FakeOHLCVRepository()
    use_case = _use_case({"NSE": FakeProvider([_raw("INFY")])}, [_security(7, "INFY")], repo)

    await use_case.execute(["NSE"])
    await use_case.execute(["NSE"])

    assert len(repo.bars) == 1


@pytest.mark.asyncio
async def test_unmapped_symbol_is_counted_not_raised() -> None:
    """A bar for an unknown symbol is counted and skipped, never written."""
    repo = FakeOHLCVRepository()
    provider = FakeProvider([_raw("INFY"), _raw("NOTLISTED")])
    use_case = _use_case({"NSE": provider}, [_security(7, "INFY")], repo)

    result = (await use_case.execute(["NSE"])).results[0]

    assert result.securities_unmapped == 1
    assert result.securities_matched == 1
    assert len(repo.bars) == 1


@pytest.mark.asyncio
async def test_active_security_without_a_bar_is_counted_missing() -> None:
    """An active security the session did not print is reported as missing."""
    repo = FakeOHLCVRepository()
    securities = [_security(7, "INFY"), _security(8, "TCS")]
    use_case = _use_case({"NSE": FakeProvider([_raw("INFY")])}, securities, repo)

    result = (await use_case.execute(["NSE"])).results[0]

    assert result.securities_missing == 1


@pytest.mark.asyncio
async def test_bse_failure_does_not_fail_the_nse_half() -> None:
    """A BSE provider exception is reported on its own result only."""
    repo = FakeOHLCVRepository()
    providers = {
        "NSE": FakeProvider([_raw("INFY")]),
        "BSE": FakeProvider(error=RuntimeError("BSE archive unreachable")),
    }
    securities = [_security(7, "INFY"), _security(9, "INFY", exchange="BSE")]
    use_case = _use_case(providers, securities, repo)

    summary = await use_case.execute(["NSE", "BSE"])
    nse, bse = summary.results

    assert nse.exchange == "NSE"
    assert nse.provider_error is None
    assert nse.rows_written == 1
    assert bse.exchange == "BSE"
    assert bse.provider_error == "RuntimeError: BSE archive unreachable"
    assert bse.rows_written == 0
    assert summary.overall_status == "partial"


@pytest.mark.asyncio
async def test_bars_are_mapped_per_exchange() -> None:
    """The same ticker on two exchanges resolves to two different securities."""
    repo = FakeOHLCVRepository()
    providers = {"NSE": FakeProvider([_raw("INFY")]), "BSE": FakeProvider([_raw("INFY")])}
    securities = [_security(7, "INFY"), _security(9, "INFY", exchange="BSE")]

    await _use_case(providers, securities, repo).execute(["NSE", "BSE"])

    assert set(repo.bars) == {(7, _FRIDAY), (9, _FRIDAY)}
