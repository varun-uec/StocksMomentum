"""Calendar-aligned RS ratings (IMPLEMENTATION_SPEC §8, engine v2).

Adjusted closes (a split is not a loss, found in M14.7), session anchors with
a 5-session tolerance (owner decision S-4), the 253-bar minimum, the reference
equity universe and the (return, security_id) tie-break.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from momentum25.application.services.rs_ratings import (
    compute_universe_rs_ratings,
    resolve_universe_rs_ratings,
)
from momentum25.domain.entities.market_data import OHLCVBar, OHLCVSeries
from momentum25.domain.entities.security import Security
from momentum25.domain.value_objects.types import Symbol
from tests.unit.test_walk_forward import WeekdayCalendar

CAL = WeekdayCalendar()
DAYS = CAL.sessions_between(date(2024, 1, 1), date(2025, 3, 31))
T = DAYS[-1]
S63 = DAYS[-64]  # the 63rd session before t
WEIGHTS = {"63": 1.0}


def _bars(raw: list[Decimal], factors: list[Decimal] | None = None, skip=()) -> tuple:
    factors = factors or [Decimal(1)] * len(raw)
    return tuple(
        OHLCVBar(date=d, open=c, high=c, low=c, close=c, volume=1000, adj_factor=f, adj_close=None)
        for d, c, f in zip(DAYS, raw, factors, strict=True)
        if d not in skip
    )


def _flat(level: str = "100") -> tuple:
    return _bars([Decimal(level)] * len(DAYS))


def _step(before: str, after: str, at: date = S63, skip=()) -> tuple:
    """``before`` until ``at``, ``after`` from the session after ``at``."""
    return _bars([Decimal(before if d <= at else after) for d in DAYS], skip=skip)


class _Repo:
    def __init__(self, series: dict[int, tuple]) -> None:
        self.series = series

    async def get_series(self, security_id: int, lookback_days: int, as_of: date) -> OHLCVSeries:
        return OHLCVSeries(security_id=security_id, bars=self.series[security_id])


def _sec(sid: int, symbol: str, **kw) -> Security:
    kw.setdefault("isin", f"INE{sid:09d}")
    return Security(symbol=Symbol(symbol), name=symbol, id=sid, **kw)


async def _ratings(series: dict[int, tuple], securities: list[Security]) -> dict[str, int]:
    return await compute_universe_rs_ratings(securities, _Repo(series), T, WEIGHTS, CAL)


async def test_a_split_inside_the_lookback_is_not_a_crash() -> None:
    # SPLITTER rises 20% across a 1:5 split: raw closes fall from 500 to 120.
    raw = [Decimal(500) if d <= S63 else Decimal(120) for d in DAYS]
    factors = [Decimal("0.2") if d <= S63 else Decimal(1) for d in DAYS]
    series = {1: _bars(raw, factors), 2: _flat()}
    ratings = await _ratings(series, [_sec(1, "SPLITTER"), _sec(2, "FLAT")])
    assert ratings == {"FLAT": 1, "SPLITTER": 99}


async def test_mcx_five_for_one_split_golden_case_keeps_its_twenty_percent_gain() -> None:
    """The historical MCX failure was a raw-close 1:5 split read as a crash.

    Adjusted, the anchor on S_63 is 500 × 0.2 = 100 and t closes at 120: +20%.
    A stock that really fell 10% must rank below it.
    """
    split = DAYS[-10]
    raw = [Decimal(500) if d < split else Decimal(100) for d in DAYS[:-1]] + [Decimal(120)]
    factors = [Decimal("0.2") if d < split else Decimal(1) for d in DAYS]
    series = {1: _bars(raw, factors), 2: _step("100", "90"), 3: _flat()}
    ratings = await _ratings(series, [_sec(1, "MCX"), _sec(2, "FALLER"), _sec(3, "FLAT")])
    assert ratings == {"FALLER": 1, "FLAT": 50, "MCX": 99}


async def test_the_anchor_is_the_reference_session_not_the_sixty_third_own_bar() -> None:
    """GAPPY misses 20 sessions after S_63. Counting its own bars, its anchor
    would fall before S_63 at 50 and read +140%; on the calendar it is +20%."""
    gap = set(DAYS[-40:-20])
    before = [Decimal(50) if d < DAYS[-80] else Decimal(100) for d in DAYS]
    gappy = _bars(
        [p if d != T else Decimal(120) for d, p in zip(DAYS, before, strict=True)], skip=gap
    )
    series = {1: gappy, 2: _step("100", "130"), 3: _flat()}
    ratings = await _ratings(series, [_sec(1, "GAPPY"), _sec(2, "STRONG"), _sec(3, "FLAT")])
    assert ratings == {"FLAT": 1, "GAPPY": 50, "STRONG": 99}


async def test_an_anchor_up_to_five_sessions_early_is_used() -> None:
    # No bars on S_63 or the 4 sessions before it: the bar 5 sessions early is the anchor.
    gap = set(DAYS[-68:-63])
    series = {1: _step("100", "150", at=DAYS[-69], skip=gap), 2: _flat()}
    ratings = await _ratings(series, [_sec(1, "LATE"), _sec(2, "FLAT")])
    assert ratings == {"FLAT": 1, "LATE": 99}


async def test_an_anchor_more_than_five_sessions_early_gives_no_rating() -> None:
    gap = set(DAYS[-69:-63])
    series = {1: _step("100", "150", at=DAYS[-70], skip=gap), 2: _flat(), 3: _flat("50")}
    ratings = await _ratings(series, [_sec(1, "GONE"), _sec(2, "FLAT"), _sec(3, "FLAT50")])
    assert "GONE" not in ratings and len(ratings) == 2


async def test_fewer_than_253_bars_gives_no_rating() -> None:
    short = _flat()[-252:]
    series = {1: short, 2: _flat(), 3: _step("100", "110")}
    ratings = await _ratings(series, [_sec(1, "NEW"), _sec(2, "FLAT"), _sec(3, "UP")])
    assert ratings == {"FLAT": 1, "UP": 99}


async def test_equal_returns_break_ties_by_security_id() -> None:
    series = {7: _flat(), 3: _flat(), 5: _flat()}
    ratings = await _ratings(series, [_sec(7, "C"), _sec(3, "A"), _sec(5, "B")])
    assert ratings == {"A": 1, "B": 50, "C": 99}


async def test_read_path_ranks_the_reference_equity_universe() -> None:
    # Regression R3-B: the read paths ranked fund units too. Engine v2 adds the
    # reference universe: dual-listed BOTH rows are in, BSE-only rows and
    # names delisted by t are out, and today's active flag is not an input.
    series = {1: _step("100", "130"), 2: _flat(), 3: _step("100", "200"), 4: _step("100", "50")}
    series |= {5: _step("100", "300"), 6: _step("100", "120")}
    universe = [
        _sec(1, "NSEONLY"),
        _sec(2, "FLAT", exchange="BOTH"),
        _sec(3, "GOLDETF", isin="INF000000003"),
        _sec(4, "BSEONLY", exchange="BSE"),
        _sec(5, "DELISTED", delisting_date=T),
        _sec(6, "INACTIVE", is_active=False),
    ]

    class _Securities:
        async def list_all(self) -> list[Security]:
            return universe

    strategy = SimpleNamespace(config=SimpleNamespace(indicators={"rs_return_weights": WEIGHTS}))
    read_path = await resolve_universe_rs_ratings(
        _Securities(), _Repo(series), strategy, T, None, CAL
    )
    assert read_path == {"FLAT": 1, "INACTIVE": 50, "NSEONLY": 99}


async def test_bars_on_non_sessions_do_not_cut_the_window_short() -> None:
    """Bars on 14 exchange holidays (a fixture, a Muhurat print) must not leave
    the anchor out of reach: the RS read fetches beyond the session count."""
    holidays = set(DAYS[-300::20])

    class _Holidays:
        def sessions_between(self, start: date, end: date) -> list[date]:
            return [d for d in CAL.sessions_between(start, end) if d not in holidays]

    weights = {"252": 1.0}
    series = {1: _step("100", "130", at=DAYS[-260]), 2: _flat()}

    class _Lookback(_Repo):
        async def get_series(self, security_id: int, lookback_days: int, as_of: date):
            bars = self.series[security_id][-lookback_days:]
            return OHLCVSeries(security_id=security_id, bars=bars)

    ratings = await compute_universe_rs_ratings(
        [_sec(1, "UP"), _sec(2, "FLAT")], _Lookback(series), T, weights, _Holidays()
    )
    assert ratings == {"FLAT": 1, "UP": 99}


async def test_a_same_day_correction_is_not_served_from_the_cache() -> None:
    """R3-B-14: the cache key carries the data revision, so a correction recomputes."""

    class _Cache:
        def __init__(self) -> None:
            self.store: dict[tuple[date, str], dict[str, int]] = {}

        async def get(self, as_of: date, basis: str) -> dict[str, int] | None:
            return self.store.get((as_of, basis))

        async def set(self, as_of: date, basis: str, ratings: dict[str, int]) -> None:
            self.store[(as_of, basis)] = ratings

    class _Securities:
        async def list_all(self) -> list[Security]:
            return [_sec(1, "UP"), _sec(2, "FLAT")]

    class _Revisioned(_Repo):
        revision = 1

        async def data_revision(self) -> int:
            return self.revision

    repo = _Revisioned({1: _step("100", "130"), 2: _flat()})
    cache = _Cache()
    strategy = SimpleNamespace(config=SimpleNamespace(indicators={"rs_return_weights": WEIGHTS}))

    async def read() -> dict[str, int]:
        return await resolve_universe_rs_ratings(_Securities(), repo, strategy, T, cache, CAL)

    assert await read() == {"FLAT": 1, "UP": 99}
    repo.series[1] = _step("100", "70")  # same-day correction
    assert await read() == {"FLAT": 1, "UP": 99}  # same revision: cached
    repo.revision = 2
    assert await read() == {"FLAT": 99, "UP": 1}
