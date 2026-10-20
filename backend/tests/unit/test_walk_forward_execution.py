"""Execution method v2 (brief-addendum-execution-v2.md): one test per rule.

Deterministic fakes only. Two or three securities, so every eligible name is
in the target set and the expected trades are easy to state by hand.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from momentum25.application.use_cases.walk_forward import WalkForwardRunner
from momentum25.domain.backtest.execution import ExecutionBar
from momentum25.domain.backtest.portfolio_step import COST_BPS
from momentum25.domain.errors import LookAheadError
from tests.unit.test_walk_forward import (
    DatedUniverse,
    FakePrices,
    FixedUniverse,
    WeekdayCalendar,
    _facts,
    _rising_series,
)

HIST = date(2022, 1, 3)
F = date(2023, 3, 1)  # first session of March 2023
D = date(2023, 2, 28)  # its decision date
CAPITAL = Decimal(1_000_000)


def _series(growth: str) -> dict[date, Decimal]:
    return _rising_series(HIST, 520, Decimal(100), Decimal(growth))


def _without(series: dict[date, Decimal], *days: date) -> dict[date, Decimal]:
    return {d: p for d, p in series.items() if d not in days}


def _sessions(first: date, count: int) -> list[date]:
    return WeekdayCalendar().sessions_between(first, first + timedelta(days=3 * count))[:count]


def _run(prices: FakePrices, universe, end: date = date(2023, 3, 31)):
    return WalkForwardRunner(WeekdayCalendar(), prices, universe).run(F, end, CAPITAL)


def test_a_name_without_a_bar_on_the_decision_date_is_not_scored() -> None:
    """E1: the strongest name has no bar on D, so it cannot be selected."""
    prices = FakePrices(
        {1: _series("1.001"), 2: _series("1.0005"), 3: _without(_series("1.004"), D)}
    )
    result = _run(prices, FixedUniverse([_facts(1), _facts(2), _facts(3)]))
    first = result.rebalances[0]
    assert first.scored_count == 2
    assert 3 not in first.selected and {1, 2} <= set(first.selected)


def test_a_buy_fills_at_the_first_later_session_with_a_bar() -> None:
    """X1: no bar on F or F+1; the buy fills at F+2's open, 2 sessions late."""
    f1, f2 = _sessions(F, 3)[1:]
    prices = FakePrices({1: _series("1.001"), 2: _without(_series("1.0005"), F, f1)})
    result = _run(prices, FixedUniverse([_facts(1), _facts(2)]))
    buy = next(t for t in result.trades if t.security_id == 2)
    assert buy.fill_date == f2 and buy.order_date == F and buy.delay_sessions == 2
    assert buy.fill_price == prices.execution_bar(2, f2).adj_open  # type: ignore[union-attr]


def test_a_buy_expires_after_five_sessions_and_its_cash_stays_cash() -> None:
    """S-1: no bar on F..F+4; the buy expires and is never filled later."""
    window = _sessions(F, 5)
    prices = FakePrices({1: _series("1.001"), 2: _without(_series("1.0005"), *window)})
    result = _run(prices, FixedUniverse([_facts(1), _facts(2)]))
    assert all(t.security_id != 2 for t in result.trades)
    expired = [o for o in result.closed_orders if o.security_id == 2 and o.reason == "expired"]
    assert len(expired) == 1 and expired[0].remaining_cash > 0


def test_a_sell_retries_until_the_security_trades_again() -> None:
    """X1: a holding leaves the universe; its exit fills at the first session with a bar."""
    april_f = date(2023, 4, 3)
    blocked = _sessions(april_f, 3)
    retry = _sessions(april_f, 4)[3]
    prices = FakePrices({1: _series("1.001"), 2: _without(_series("1.0005"), *blocked)})
    universe = DatedUniverse(
        [(date(2023, 3, 15), [_facts(1), _facts(2)]), (date(9999, 1, 1), [_facts(1)])]
    )
    result = _run(prices, universe, end=date(2023, 4, 28))
    exit_fill = next(t for t in result.trades if t.security_id == 2 and t.side == "SELL")
    assert exit_fill.order_date == april_f and exit_fill.fill_date == retry
    assert exit_fill.delay_sessions == 3


def test_a_fill_is_capped_at_ten_percent_of_the_sessions_traded_value() -> None:
    """S-3: thin turnover splits the buy into partial fills over the buy window."""
    window = _sessions(F, 5)
    thin = {(1, d): Decimal(100_000) for d in window}
    prices = FakePrices({1: _series("1.001"), 2: _series("1.0005")}, turnover=thin)
    result = _run(prices, FixedUniverse([_facts(1), _facts(2)]))
    fills = [t for t in result.trades if t.security_id == 1]
    assert [t.fill_date for t in fills] == window
    assert all(t.notional == Decimal(10_000) and t.participation == Decimal("0.1") for t in fills)
    assert all(t.partial for t in fills)
    assert any(o.security_id == 1 and o.reason == "expired" for o in result.closed_orders)


def test_stuck_positions_never_create_leverage_and_are_flagged_at_the_end() -> None:
    """C1 and S-6: a holding stops trading; buys scale to the cash there is,
    and the holding is reported as non-trading with a lower bound."""
    last_bar = date(2023, 3, 15)
    stuck = {d: p for d, p in _series("1.0005").items() if d <= last_bar}
    prices = FakePrices({1: _series("1.001"), 2: stuck, 3: _series("1.0008")})
    universe = DatedUniverse(
        [(date(2023, 3, 15), [_facts(1), _facts(2)]), (date(9999, 1, 1), [_facts(1), _facts(3)])]
    )
    result = _run(prices, universe, end=date(2023, 5, 31))
    april = result.rebalances[1]
    assert april.buy_scale < 1  # sid 2's value cannot be sold to fund the buys
    held = {h.security_id: h for h in result.nontrading_holdings}
    assert set(held) == {2} and held[2].last_bar_date == last_bar
    assert held[2].identity_status == "no verified identity link"
    assert result.lower_bound_nav == result.final_nav - held[2].value
    assert any(o.security_id == 2 and o.reason == "open_at_end" for o in result.closed_orders)


def test_costs_are_charged_on_filled_notional_only() -> None:
    window = _sessions(F, 5)
    prices = FakePrices({1: _series("1.001"), 2: _without(_series("1.0005"), *window)})
    result = _run(prices, FixedUniverse([_facts(1), _facts(2)]))
    assert (
        sum(t.cost for t in result.trades) == sum(abs(t.notional) for t in result.trades) * COST_BPS
    )


def test_every_fill_is_priced_from_a_bar_dated_on_its_fill_session() -> None:
    blocked = _sessions(F, 2)
    prices = FakePrices({1: _series("1.001"), 2: _without(_series("1.0005"), *blocked)})
    result = _run(prices, FixedUniverse([_facts(1), _facts(2)]), end=date(2023, 6, 30))
    for t in result.trades:
        bar = prices.execution_bar(t.security_id, t.fill_date)
        assert bar is not None and t.fill_price == bar.adj_open


def test_an_execution_bar_dated_after_its_session_is_rejected() -> None:
    class LeakyBars(FakePrices):
        def execution_bar(self, security_id: int, session: date) -> ExecutionBar | None:
            bar = super().execution_bar(security_id, session)
            if bar is None or session != F:
                return bar
            return ExecutionBar(
                session + timedelta(days=1),
                bar.adj_open,
                bar.adj_high,
                bar.adj_low,
                bar.adj_close,
                bar.volume,
                bar.turnover_value,
            )

    prices = LeakyBars({1: _series("1.001"), 2: _series("1.0005")})
    with pytest.raises(LookAheadError):
        _run(prices, FixedUniverse([_facts(1), _facts(2)]))


def test_the_result_names_its_method_and_policy() -> None:
    result = _run(FakePrices({1: _series("1.001")}), FixedUniverse([_facts(1)]))
    assert result.method_version == 2
    assert result.execution_policy is not None
    assert result.execution_policy["buy_window_sessions"] == 5
    assert result.execution_policy["participation_cap"] == "0.10"
    assert result.execution_policy["same_session_settlement"] is True
