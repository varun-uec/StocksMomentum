"""Walk-forward runner tests — make reviewer checklist items 7, 8, 10, 13, 14
runnable (see handoff/brief-addendum-loop2.md §4).

Every provider here is a deterministic in-memory fake. No network, no DB, no
clock. The point is to exercise the *seam* — as-of enforcement, fill timing,
point-in-time universe, independent NAV reconstruction — not the frozen math.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from momentum25.application.use_cases.walk_forward import (
    LookAheadError,
    WalkForwardResult,
    WalkForwardRunner,
    _reconstruct_nav_from_trades,
    format_walk_forward_report,
)
from momentum25.domain.backtest.eligibility import EligibilityFacts
from momentum25.domain.ports.walk_forward import PricePoint

# ── Fakes ──────────────────────────────────────────────────────────────────


class WeekdayCalendar:
    """Every Mon-Fri is a session. Enough for deterministic monthly rebalances."""

    def is_session(self, day: date) -> bool:
        return day.weekday() < 5

    def sessions_between(self, start: date, end: date) -> list[date]:
        out: list[date] = []
        d = start
        while d <= end:
            if self.is_session(d):
                out.append(d)
            d += timedelta(days=1)
        return out

    def next_session(self, after: date) -> date:
        d = after + timedelta(days=1)
        while not self.is_session(d):
            d += timedelta(days=1)
        return d


class FakePrices:
    """Deterministic per-security adjusted-close series with an as-of spy."""

    def __init__(self, series: dict[int, dict[date, Decimal]]) -> None:
        self._series = {sid: dict(sorted(s.items())) for sid, s in series.items()}
        self.calls: list[tuple[int, date, date]] = []  # spy for item 13

    def price_on_or_before(
        self, security_id: int, target: date, as_of: date
    ) -> PricePoint | None:
        self.calls.append((security_id, target, as_of))
        horizon = min(target, as_of)
        best: date | None = None
        for d in self._series.get(security_id, {}):
            if d <= horizon and (best is None or d > best):
                best = d
        if best is None:
            return None
        return PricePoint(security_id, best, self._series[security_id][best])


class LeakyPrices:
    """A provider that always answers with a price dated one day after as_of."""

    def price_on_or_before(
        self, security_id: int, target: date, as_of: date
    ) -> PricePoint | None:
        return PricePoint(security_id, as_of + timedelta(days=1), Decimal(100))


class FixedUniverse:
    """Returns the same facts for every decision date."""

    def __init__(self, facts: list[EligibilityFacts]) -> None:
        self._facts = facts

    def facts_as_of(self, decision_date: date) -> list[EligibilityFacts]:
        return list(self._facts)


class DatedUniverse:
    """Point-in-time universe: facts vary by decision date (survivorship test)."""

    def __init__(self, by_cutoff: list[tuple[date, list[EligibilityFacts]]]) -> None:
        # (cutoff, facts): facts apply for decision_date < cutoff.
        self._by_cutoff = sorted(by_cutoff)

    def facts_as_of(self, decision_date: date) -> list[EligibilityFacts]:
        for cutoff, facts in self._by_cutoff:
            if decision_date < cutoff:
                return list(facts)
        return []


def _facts(security_id: int, in_index: bool = True) -> EligibilityFacts:
    return EligibilityFacts(
        security_id=security_id,
        listing_days_as_of_decision_date=400,
        is_t2t=False,
        is_under_surveillance=False,
        in_nifty_500=in_index,
    )


def _rising_series(start: date, days: int, base: Decimal, growth: Decimal) -> dict[date, Decimal]:
    cal = WeekdayCalendar()
    out: dict[date, Decimal] = {}
    price = base
    d = start
    n = 0
    while n < days:
        if cal.is_session(d):
            out[d] = price
            price *= growth
            n += 1
        d += timedelta(days=1)
    return out


# ── Tests ────────────────────────────────────────────────────────────────


def _build_runner() -> tuple[WalkForwardRunner, date, date]:
    hist_start = date(2022, 1, 3)
    a = _rising_series(hist_start, 500, Decimal(100), Decimal("1.002"))  # strong up
    b = _rising_series(hist_start, 500, Decimal(100), Decimal("1.0005"))  # mild up
    prices = FakePrices({1: a, 2: b})
    universe = FixedUniverse([_facts(1), _facts(2)])
    runner = WalkForwardRunner(WeekdayCalendar(), prices, universe)
    return runner, date(2023, 3, 1), date(2023, 8, 31)


def test_fill_date_strictly_after_decision_date():
    """Item 10: decide at close t, fill at t+1 (next session). Never same-day."""
    runner, start, end = _build_runner()
    result = runner.run(start, end, Decimal(1_000_000))
    assert result.rebalances
    for rb in result.rebalances:
        assert rb.fill_date > rb.decision_date
        for tr in rb.trades:
            assert tr.fill_date == rb.fill_date
            assert tr.fill_date > rb.decision_date


def test_look_ahead_provider_is_rejected():
    """Item 7: a provider that leaks a post-decision price must be caught."""
    universe = FixedUniverse([_facts(1)])
    runner = WalkForwardRunner(WeekdayCalendar(), LeakyPrices(), universe)
    with pytest.raises(LookAheadError):
        runner.run(date(2023, 3, 1), date(2023, 5, 31), Decimal(1_000_000))


def test_survivorship_point_in_time_universe_used():
    """Item 8: a name in the index only for early dates must be scored then,
    and absent once it leaves — proving the runner uses point-in-time facts."""
    hist_start = date(2022, 1, 3)
    survivor = _rising_series(hist_start, 500, Decimal(100), Decimal("1.001"))
    delisted = _rising_series(hist_start, 500, Decimal(100), Decimal("1.0015"))
    prices = FakePrices({1: survivor, 2: delisted})
    cutoff = date(2023, 6, 1)  # security 2 leaves the index from this decision date
    universe = DatedUniverse(
        [
            (cutoff, [_facts(1), _facts(2)]),  # before cutoff: both in
            (date(9999, 1, 1), [_facts(1)]),  # after: only survivor
        ]
    )
    runner = WalkForwardRunner(WeekdayCalendar(), prices, universe)
    result = runner.run(date(2023, 3, 1), date(2023, 8, 31), Decimal(1_000_000))

    early = [rb for rb in result.rebalances if rb.decision_date < cutoff]
    late = [rb for rb in result.rebalances if rb.decision_date >= cutoff]
    assert early and late
    assert any(2 in rb.selected for rb in early)  # used while in index
    assert all(2 not in rb.selected for rb in late)  # gone once it left


def test_reconstructed_nav_matches_independent_replay():
    """Item 14: recompute terminal NAV from the trade log, outside the engine."""
    runner, start, end = _build_runner()
    capital = Decimal(1_000_000)
    result = runner.run(start, end, capital)

    # Independent replay in the test itself, not calling the engine's summary.
    cash = capital
    qty: dict[int, Decimal] = {}
    for t in sorted(result.trades, key=lambda x: (x.fill_date, x.security_id)):
        cash -= t.notional + t.cost
        qty[t.security_id] = qty.get(t.security_id, Decimal(0)) + t.quantity
    nav = cash
    prices = runner._prices  # the fake; read last price at end independently
    for sid, held in qty.items():
        point = prices.price_on_or_before(sid, end, end)
        assert point is not None
        nav += held * point.adj_close

    assert nav == result.final_nav
    assert result.total_return == result.final_nav / capital - 1


def test_asof_enforcement_runs_on_real_path():
    """Item 13: the as-of'd price call actually fires during a real run, with
    as_of == the decision date (not some unused branch)."""
    runner, start, end = _build_runner()
    prices = runner._prices
    result = runner.run(start, end, capital := Decimal(1_000_000))
    assert result.final_nav > 0 and capital > 0
    decision_dates = {rb.decision_date for rb in result.rebalances}
    scored_as_of = {as_of for (_sid, _target, as_of) in prices.calls}
    # Every decision date drove at least one as-of'd price fetch.
    assert decision_dates <= scored_as_of


def test_run_is_deterministic():
    """Same inputs -> identical outputs (determinism contract)."""
    r1, start, end = _build_runner()
    r2, _, _ = _build_runner()
    a = r1.run(start, end, Decimal(1_000_000))
    b = r2.run(start, end, Decimal(1_000_000))
    assert a.final_nav == b.final_nav
    assert a.total_return == b.total_return
    assert [rb.selected for rb in a.rebalances] == [rb.selected for rb in b.rebalances]


def test_reconstruct_helper_ignores_engine_bookkeeping():
    """The reconstruction fn depends only on trades + prices, nothing else."""
    runner, start, end = _build_runner()
    result = runner.run(start, end, Decimal(1_000_000))
    independent = _reconstruct_nav_from_trades(
        list(result.trades), Decimal(1_000_000), runner._prices, end
    )
    assert independent == result.final_nav


def _sample_result(benchmark_return, benchmark_label) -> WalkForwardResult:
    return WalkForwardResult(
        rebalances=(),
        trades=(),
        initial_capital=Decimal(1_000_000),
        final_nav=Decimal(1_100_000),
        total_return=Decimal("0.10"),
        benchmark_return=benchmark_return,
        benchmark_label=benchmark_label,
    )


def test_report_carries_benchmark_label_next_to_the_number():
    """Checklist item 14 / brief-addendum-approximations.md: the label must
    sit next to the benchmark number in the one output surface that prints
    it, not just live on the dataclass field."""
    result = _sample_result(Decimal("0.05"), "Nifty 500 Price Index (not TRI)")
    report = format_walk_forward_report(result)
    line = next(line for line in report.splitlines() if "Benchmark return" in line)
    assert "Nifty 500 Price Index (not TRI)" in line
    assert "5.00%" in line


def test_report_never_prints_benchmark_number_without_a_label():
    """A missing label must not silently disappear behind the number."""
    result = _sample_result(Decimal("0.05"), None)
    report = format_walk_forward_report(result)
    line = next(line for line in report.splitlines() if "Benchmark return" in line)
    assert "UNLABELED BENCHMARK" in line


def test_report_omits_benchmark_line_when_no_benchmark_bound():
    result = _sample_result(None, None)
    report = format_walk_forward_report(result)
    assert "Benchmark return" not in report


def test_reversed_date_range_is_rejected():
    """Regression (B3-001): start > end must fail loudly, not report a
    spurious zero-rebalance, zero-return run."""
    runner, start, end = _build_runner()
    with pytest.raises(ValueError, match="start must be on or before end"):
        runner.run(end, start, Decimal(1_000_000))
