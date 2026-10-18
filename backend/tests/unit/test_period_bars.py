"""Golden tests for weekly and monthly bars (ADR-013 §4, M11b, M13).

One bar per ISO week or calendar month of NSE sessions: open of the first session, highest high,
lowest low, close of the last session, summed volume, dated at the last session.
Every expected value below is worked out by hand.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from momentum25.application.use_cases.securities import GetSecurityOHLCV, interval_bars
from momentum25.application.use_cases.stocks import GetIndicatorSeries
from momentum25.domain.entities.market_data import (
    OHLCVBar,
    OHLCVSeries,
    period_bars,
    series_data_version,
)
from momentum25.domain.entities.security import Security
from momentum25.domain.value_objects.types import Symbol
from momentum25.infrastructure.pipelines.indicator_pipeline import IndicatorPipelineImpl


def _bar(day: date, o: str, h: str, low: str, c: str, v: int, factor: str = "1") -> OHLCVBar:
    return OHLCVBar(
        date=day,
        open=Decimal(o),
        high=Decimal(h),
        low=Decimal(low),
        close=Decimal(c),
        volume=v,
        adj_factor=Decimal(factor),
    )


def _weekdays(monday: date) -> list[date]:
    return [monday + timedelta(days=i) for i in range(5)]


def test_a_holiday_week_is_one_bar_dated_at_its_last_session() -> None:
    # Week of 2025-10-20; Wednesday 22nd is a holiday.
    sessions = [date(2025, 10, 20), date(2025, 10, 21), date(2025, 10, 23), date(2025, 10, 24)]
    daily = [
        _bar(sessions[0], "100", "105", "99", "104", 10),
        _bar(sessions[1], "104", "110", "103", "108", 20),
        _bar(sessions[2], "108", "109", "95", "97", 30),
        _bar(sessions[3], "97", "101", "96", "100", 40),
    ]
    [week] = period_bars(daily, sessions, "week")
    assert week.bar == _bar(date(2025, 10, 24), "100", "110", "95", "100", 100)
    assert week.partial is False


def test_a_week_still_running_is_partial() -> None:
    sessions = _weekdays(date(2026, 8, 3))
    daily = [_bar(d, "10", "12", "9", "11", 5) for d in sessions[:3]]  # Mon-Wed so far
    [week] = period_bars(daily, sessions, "week")
    assert week.bar.date == date(2026, 8, 5)
    assert week.partial is True


def test_a_week_with_no_sessions_has_no_bar() -> None:
    first, third = date(2026, 3, 2), date(2026, 3, 16)
    sessions = _weekdays(first) + _weekdays(third)  # the week of 9 March is closed
    daily = [_bar(d, "10", "11", "9", "10", 1) for d in sessions]
    bars = period_bars(daily, sessions, "week")
    assert [w.bar.date for w in bars] == [date(2026, 3, 6), date(2026, 3, 20)]


def test_iso_weeks_cross_the_new_year() -> None:
    # 29 Dec 2025 - 2 Jan 2026 is ISO week 2026-W01: one bar, not two.
    sessions = _weekdays(date(2025, 12, 29))
    daily = [_bar(d, "10", "11", "9", "10", 1) for d in sessions]
    [week] = period_bars(daily, sessions, "week")
    assert week.bar.date == date(2026, 1, 2)
    assert week.bar.volume == 5


def test_a_corporate_action_week_has_no_jump_inside_it() -> None:
    """A 1:1 bonus goes ex on Wednesday: raw prints halve, adjusted ones do not."""
    sessions = _weekdays(date(2026, 6, 1))
    raw = [
        _bar(sessions[0], "200", "204", "198", "202", 100, "0.5"),
        _bar(sessions[1], "202", "206", "200", "204", 100, "0.5"),
        _bar(sessions[2], "102", "104", "101", "103", 200),
        _bar(sessions[3], "103", "105", "102", "104", 200),
        _bar(sessions[4], "104", "106", "103", "105", 200),
    ]
    with pytest.raises(ValueError, match="adjusted"):
        period_bars(raw, sessions, "week")  # raw prints would give a high of 206
    [week] = period_bars([b.adjusted() for b in raw], sessions, "week")
    assert (week.bar.open, week.bar.high, week.bar.low, week.bar.close) == (
        Decimal("100.0000"),
        Decimal("106"),
        Decimal("99.0000"),
        Decimal("105"),
    )
    assert week.bar.volume == 1000  # 200 + 200 adjusted, plus 600


def test_a_month_is_one_bar_across_its_weeks() -> None:
    # March 2026: 22 weekday sessions over five ISO weeks.
    march = (date(2026, 3, 1) + timedelta(days=n) for n in range(31))
    sessions = [d for d in march if d.weekday() < 5]
    daily = [
        _bar(d, str(100 + i), str(110 + i), str(90 - i), str(105 + i), 1)
        for i, d in enumerate(sessions)
    ]
    [month] = period_bars(daily, sessions, "month")
    assert month.bar == _bar(date(2026, 3, 31), "100", "131", "69", "126", 22)
    assert month.partial is False


def test_months_split_where_a_week_does_not() -> None:
    # 29 Dec 2025 - 2 Jan 2026 is one ISO week but two months.
    sessions = _weekdays(date(2025, 12, 29))
    daily = [_bar(d, "10", "11", "9", "10", 1) for d in sessions]
    months = period_bars(daily, sessions, "month")
    assert [b.bar.date for b in months] == [date(2025, 12, 31), date(2026, 1, 2)]
    assert len(period_bars(daily, sessions, "week")) == 1


def test_the_running_month_is_partial_even_in_december() -> None:
    first_half = (date(2025, 12, 1) + timedelta(days=n) for n in range(15))
    days = [d for d in first_half if d.weekday() < 5]
    series = OHLCVSeries(1, tuple(_bar(d, "10", "11", "9", "10", 1) for d in days))
    [(bar, partial)] = interval_bars(series, "1M", _Calendar())  # type: ignore[arg-type]
    assert (bar.date, partial) == (date(2025, 12, 15), True)


def test_the_data_version_follows_every_stored_input() -> None:
    bars = [_bar(date(2026, 8, 3), "10", "11", "9", "10", 1, "0.5")]
    base = series_data_version(bars, 2)
    assert base == series_data_version(list(bars), 2)  # deterministic
    assert len(base) == 12
    refreshed = [_bar(date(2026, 8, 3), "10", "11", "9", "10", 1, "0.25")]
    corrected = [_bar(date(2026, 8, 3), "10", "11", "9", "10.5", 1, "0.5")]
    assert len({base, series_data_version(refreshed, 2), series_data_version(corrected, 2)}) == 3
    assert series_data_version(bars, 3) != base


# ── the use cases ─────────────────────────────────────────────────────────

_START = date(2025, 1, 6)  # a Monday
_DAILY = tuple(
    _bar(d, str(100 + i), str(101 + i), str(99 + i), str(100 + (i % 7)), 1000)
    for i, d in enumerate(
        d for d in (_START + timedelta(days=n) for n in range(420)) if d.weekday() < 5
    )
)


class _Calendar:
    def sessions_between(self, start: date, end: date) -> list[date]:
        return [
            start + timedelta(days=n)
            for n in range((end - start).days + 1)
            if (start + timedelta(days=n)).weekday() < 5
        ]


class _Securities:
    async def get_by_symbol(self, symbol: str) -> Security:
        return Security(symbol=Symbol(symbol), name="Test", id=1)


class _Ohlcv:
    async def get_series(self, security_id: int, lookback_days: int, as_of: date) -> OHLCVSeries:
        return OHLCVSeries(security_id=security_id, bars=_DAILY)


class _Strategies:
    async def get_active(self, name: str) -> SimpleNamespace:
        return SimpleNamespace(id=1, config=SimpleNamespace(indicators={}))


async def test_weekly_indicators_are_computed_on_weekly_bars() -> None:
    use_case = GetIndicatorSeries(
        _Securities(),
        _Strategies(),
        IndicatorPipelineImpl,
        _Ohlcv(),
        _Calendar(),  # type: ignore[arg-type]
    )
    weekly = await use_case.execute("TEST", interval="1W")
    expected_bars = [b for b, _ in interval_bars(OHLCVSeries(1, _DAILY), "1W", _Calendar())]  # type: ignore[arg-type]
    expected = IndicatorPipelineImpl.series_from_bars(expected_bars, date.today())
    assert [b.date for b in weekly.bars] == [b.date for b in expected_bars]
    assert [b.rsi14 for b in weekly.bars] == list(expected.rsi14)
    assert weekly.bars[-1].rsi14 is not None

    # Not daily RSI sampled at week ends: that would be a resample.
    daily = IndicatorPipelineImpl.series_from_bars(list(_DAILY), date.today())
    at_week_end = dict(zip(daily.dates, daily.rsi14, strict=True))
    assert [b.rsi14 for b in weekly.bars][-10:] != [at_week_end[b.date] for b in weekly.bars][-10:]


async def test_price_and_indicator_series_share_one_data_version() -> None:
    prices = await GetSecurityOHLCV(_Securities(), _Ohlcv(), _Calendar()).execute(  # type: ignore[arg-type]
        "TEST", to=date(2030, 1, 1), interval="1W"
    )
    series = await GetIndicatorSeries(
        _Securities(),
        _Strategies(),
        IndicatorPipelineImpl,
        _Ohlcv(),
        _Calendar(),  # type: ignore[arg-type]
    ).execute("TEST", interval="1W")
    assert prices.interval == series.interval == "1W"
    assert prices.data_version == series.data_version
    assert len(prices.bars) == 60  # 420 calendar days from a Monday: 60 full weeks


async def test_monthly_indicators_are_computed_on_monthly_bars() -> None:
    monthly = await GetIndicatorSeries(
        _Securities(),
        _Strategies(),
        IndicatorPipelineImpl,
        _Ohlcv(),
        _Calendar(),  # type: ignore[arg-type]
    ).execute("TEST", interval="1M")
    expected_bars = [b for b, _ in interval_bars(OHLCVSeries(1, _DAILY), "1M", _Calendar())]  # type: ignore[arg-type]
    expected = IndicatorPipelineImpl.series_from_bars(expected_bars, date.today())
    assert monthly.interval == "1M"
    # January 2025 to February 2026; February ends on a Saturday, so no month is partial.
    assert len(expected_bars) == 14
    # The series starts on Monday 6 January: 20 sessions, the 20th (i=19) closing at 100 + 19 % 7.
    assert expected_bars[0] == _bar(date(2025, 1, 31), "100", "120", "99", "105", 20000)
    assert [b.date for b in monthly.bars] == [b.date for b in expected_bars]
    assert [b.atr14 for b in monthly.bars] == list(expected.atr14)
