"""RS ratings use adjusted closes: a split is not a loss (found in M14.7)."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from momentum25.application.services.rs_ratings import compute_universe_rs_ratings
from momentum25.domain.entities.market_data import OHLCVBar, OHLCVSeries
from momentum25.domain.entities.security import Security
from momentum25.domain.value_objects.types import Symbol

DAYS = [date(2025, 1, 1) + timedelta(days=i) for i in range(80)]


def _bars(raw: list[Decimal], factors: list[Decimal]) -> tuple[OHLCVBar, ...]:
    return tuple(
        OHLCVBar(
            date=d,
            open=c,
            high=c,
            low=c,
            close=c,
            volume=1000,
            adj_factor=f,
            adj_close=c * f,
        )
        for d, c, f in zip(DAYS, raw, factors, strict=True)
    )


class _Repo:
    def __init__(self) -> None:
        # SPLITTER rises 20% but splits 1:5 halfway: raw closes fall from 500 to 120.
        raw = [Decimal(500 + i) if i < 40 else Decimal(100 + i / 2) for i in range(80)]
        factors = [Decimal("0.2") if i < 40 else Decimal(1) for i in range(80)]
        flat = [Decimal(100)] * 80
        self.series = {1: _bars(raw, factors), 2: _bars(flat, [Decimal(1)] * 80)}

    async def get_series(self, security_id: int, lookback_days: int, as_of: date) -> OHLCVSeries:
        return OHLCVSeries(security_id=security_id, bars=self.series[security_id])


async def test_a_split_inside_the_lookback_is_not_a_crash() -> None:
    universe = [
        Security(symbol=Symbol("SPLITTER"), name="s", id=1),
        Security(symbol=Symbol("FLAT"), name="f", id=2),
    ]
    ratings = await compute_universe_rs_ratings(universe, _Repo(), DAYS[-1], {"63": 1.0})
    assert ratings["SPLITTER"] > ratings["FLAT"]
