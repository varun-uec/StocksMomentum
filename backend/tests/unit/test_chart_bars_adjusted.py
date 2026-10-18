"""The chart's bars use the same adjusted basis as screening (ADR-013 §4).

Regression: ``/securities/{symbol}/ohlcv`` served raw prints while the
indicator pipeline multiplies by ``adj_factor``. After a 1:5 split the chart
showed pre-split prices five times the level every rule saw (M11 review,
2026-10-18). 327,225 bars over 478 securities had a factor other than 1.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from momentum25.application.use_cases.securities import GetSecurityOHLCV
from momentum25.domain.entities.market_data import OHLCVBar, OHLCVSeries
from momentum25.domain.entities.security import Security
from momentum25.domain.value_objects.types import Symbol
from momentum25.infrastructure.pipelines.indicator_pipeline import IndicatorPipelineImpl

_SPLIT = date(2026, 3, 2)


def _bar(day: date, close: str, factor: str) -> OHLCVBar:
    c = Decimal(close)
    return OHLCVBar(
        date=day,
        open=c - 1,
        high=c + 2,
        low=c - 2,
        close=c,
        volume=1000,
        prev_close=c,
        turnover_value=Decimal(5),
        adj_factor=Decimal(factor),
    )


# Before the 1:5 split the raw close is ~500 and the factor 0.2; after it ~100 and 1.
_BARS = tuple(
    _bar(_SPLIT + timedelta(days=i), "500.10" if i < 0 else "100.10", "0.2" if i < 0 else "1")
    for i in range(-3, 3)
)


def test_adjusted_scales_prices_and_volume_by_the_factor() -> None:
    adjusted = _bar(_SPLIT, "500.10", "0.2").adjusted()
    assert (adjusted.open, adjusted.high, adjusted.low, adjusted.close) == (
        Decimal("99.8200"),
        Decimal("100.4200"),
        Decimal("99.6200"),
        Decimal("100.0200"),
    )
    assert adjusted.volume == 5000
    assert adjusted.adj_factor == 1
    assert adjusted.prev_close is None  # no single adjusted meaning across an ex-date


def test_a_factor_of_one_returns_the_bar_unchanged() -> None:
    bar = _bar(_SPLIT, "100.10", "1")
    assert bar.adjusted() is bar


class _Securities:
    async def get_by_symbol(self, symbol: str) -> Security:
        return Security(symbol=Symbol(symbol), name="Test", id=1)


class _Ohlcv:
    async def get_series(self, security_id: int, lookback_days: int, as_of: date) -> OHLCVSeries:
        return OHLCVSeries(security_id=security_id, bars=_BARS)


async def test_chart_bars_have_no_jump_across_a_split() -> None:
    result = await GetSecurityOHLCV(_Securities(), _Ohlcv()).execute(  # type: ignore[arg-type]
        "TEST", to=date(2030, 1, 1)
    )
    closes = [bar.close for bar in result.bars]
    assert closes == [Decimal("100.0200")] * 3 + [Decimal("100.10")] * 3


async def test_chart_bars_match_the_screening_pipeline_bar_for_bar() -> None:
    """One authority: the chart's adjusted bars equal what the indicator pipeline reads."""
    chart = await GetSecurityOHLCV(_Securities(), _Ohlcv()).execute(  # type: ignore[arg-type]
        "TEST", to=date(2030, 1, 1)
    )
    rows = [
        SimpleNamespace(
            date=b.date,
            open=b.open,
            high=b.high,
            low=b.low,
            close=b.close,
            volume=b.volume,
            adj_factor=b.adj_factor,
        )
        for b in _BARS
    ]
    frame = IndicatorPipelineImpl._to_dataframe(rows)
    for bar, (_, row) in zip(chart.bars, frame.iterrows(), strict=True):
        for field in ("open", "high", "low", "close"):
            assert float(getattr(bar, field)) == pytest.approx(row[field], abs=1e-4)
        assert bar.volume == pytest.approx(row["volume"], abs=0.5)


def test_adjusting_twice_changes_nothing() -> None:
    """An adjusted bar carries factor 1, so no path can scale it a second time."""
    once = _bar(_SPLIT, "500.10", "0.2").adjusted()
    assert once.adjusted() is once


async def test_the_schedule_covers_dates_before_the_requested_range() -> None:
    """A drawing can sit before the visible range; its factor must still be known."""
    result = await GetSecurityOHLCV(_Securities(), _Ohlcv()).execute(  # type: ignore[arg-type]
        "TEST", from_=_SPLIT, to=date(2030, 1, 1)
    )
    assert result.bars[0].date == _SPLIT
    assert [(s.until, s.factor) for s in result.adjustments] == [
        (_SPLIT - timedelta(days=1), Decimal("0.2")),
        (_SPLIT + timedelta(days=2), Decimal(1)),
    ]


def test_a_series_with_no_action_has_one_step() -> None:
    series = OHLCVSeries(security_id=1, bars=_BARS[3:])
    assert [(s.until, s.factor) for s in series.adjustment_schedule()] == [
        (_SPLIT + timedelta(days=2), Decimal(1))
    ]
