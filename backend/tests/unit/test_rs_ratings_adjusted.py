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


async def test_mcx_five_for_one_split_golden_case_keeps_its_twenty_percent_gain() -> None:
    """The historical MCX failure was a raw-close 1:5 split read as a crash."""
    split_index = 70
    raw = [Decimal("500")] * split_index + [Decimal("100")] * 9 + [Decimal("120")]
    factors = [Decimal("0.2")] * split_index + [Decimal("1")] * (len(DAYS) - split_index)
    mcx = _bars(raw, factors)
    flat = _bars([Decimal("100")] * len(DAYS), [Decimal("1")] * len(DAYS))

    adjusted_start = mcx[-64].adj_close
    adjusted_end = mcx[-1].adj_close
    assert adjusted_start == Decimal("100")
    assert adjusted_end == Decimal("120")
    assert (adjusted_end / adjusted_start - 1) == Decimal("0.20")

    class McxRepo:
        async def get_series(
            self, security_id: int, lookback_days: int, as_of: date
        ) -> OHLCVSeries:
            return OHLCVSeries(security_id, mcx if security_id == 1 else flat)

    universe = [
        Security(symbol=Symbol("MCX"), name="Synthetic MCX", id=1),
        Security(symbol=Symbol("FLAT"), name="Flat control", id=2),
    ]
    ratings = await compute_universe_rs_ratings(universe, McxRepo(), DAYS[-1], {"63": 1.0})
    assert ratings["MCX"] == 99
    assert ratings["FLAT"] == 1


async def test_read_path_ranks_the_same_equity_universe_as_the_screening_run() -> None:
    # Regression R3-B: /stocks/{symbol}/live and the watchlist ranked RS across
    # every active security, fund and ETF units included; the run ranks equities
    # only. On 2026-10-19 data 2,679 equities got a different rating and 101
    # crossed the RS >= 70 gate.
    from types import SimpleNamespace

    from momentum25.application.services.rs_ratings import resolve_universe_rs_ratings

    repo = _Repo()
    repo.series[3] = _bars([Decimal(100 + i) for i in range(80)], [Decimal(1)] * 80)
    universe = [
        Security(symbol=Symbol("SPLITTER"), name="s", id=1, isin="INE000000001"),
        Security(symbol=Symbol("FLAT"), name="f", id=2, isin="INE000000002"),
        Security(symbol=Symbol("GOLDETF"), name="g", id=3, isin="INF000000003"),
    ]

    class _Securities:
        async def list_active(self) -> list[Security]:
            return universe

    indicators = {"rs_return_weights": {"63": 1.0}}
    strategy = SimpleNamespace(name="t", config=SimpleNamespace(indicators=indicators))
    read_path = await resolve_universe_rs_ratings(_Securities(), repo, strategy, DAYS[-1], None)
    run_path = await compute_universe_rs_ratings(universe[:2], repo, DAYS[-1], {"63": 1.0})

    assert read_path == run_path
    assert "GOLDETF" not in read_path
