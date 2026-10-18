"""The chart's MAX range must return the whole stored series.

Regression: with no ``from`` date the use case capped the series at 500 rows
(about two years), so the chart's MAX button never showed full history
(found by the NFR-11 measurement, 2026-10-18).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from momentum25.application.use_cases.securities import GetSecurityOHLCV
from momentum25.domain.entities.market_data import OHLCVBar, OHLCVSeries
from momentum25.domain.entities.security import Security
from momentum25.domain.value_objects.types import Symbol

_START = date(2016, 1, 1)
_BARS = tuple(
    OHLCVBar(
        date=_START + timedelta(days=i),
        open=Decimal(1),
        high=Decimal(1),
        low=Decimal(1),
        close=Decimal(1),
        volume=1,
    )
    for i in range(2600)
)


class _Securities:
    async def get_by_symbol(self, symbol: str) -> Security:
        return Security(symbol=Symbol(symbol), name="Test", id=1)


class _Ohlcv:
    def __init__(self) -> None:
        self.lookbacks: list[int] = []

    async def get_series(self, security_id: int, lookback_days: int, as_of: date) -> OHLCVSeries:
        self.lookbacks.append(lookback_days)
        kept = [b for b in _BARS if b.date <= as_of][-lookback_days:]
        return OHLCVSeries(security_id=security_id, bars=tuple(kept))


async def test_no_from_date_returns_every_stored_bar() -> None:
    ohlcv = _Ohlcv()
    result = await GetSecurityOHLCV(_Securities(), ohlcv, None).execute(  # type: ignore[arg-type]
        "TEST", to=date(2030, 1, 1)
    )
    assert len(result.bars) == 2600
    assert result.bars[0].date == _START


async def test_a_from_date_still_bounds_the_series() -> None:
    result = await GetSecurityOHLCV(_Securities(), _Ohlcv(), None).execute(  # type: ignore[arg-type]
        "TEST", from_=date(2022, 1, 1), to=date(2030, 1, 1)
    )
    assert result.bars[0].date == date(2022, 1, 1)
