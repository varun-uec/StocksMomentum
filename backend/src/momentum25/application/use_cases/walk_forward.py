"""Walk-forward backtest runner (execution method v2).

Wires the frozen ``domain/backtest/`` signal, ranking and buffer math to real,
point-in-time historical data, and executes through the fill-driven ledger in
``domain/backtest/execution.py``.

Ground truth: ``docs/history/backtest-loop/brief.md`` and its addenda, the last
being ``brief-addendum-execution-v2.md`` (2026-10-20):

- Decide at the close of the last session of month M-1 (D). A security is
  scored only with a valid bar dated D (E1).
- Plan at the first session of month M (F). Orders fill at the adjusted open of
  the first valid execution bar on or after F: buys within the buy window,
  sells until filled. Each fill is capped at a share of the session's traded
  value; the rest waits. A new plan supersedes every live order.
- Holdings and cash change only through fills. NAV is valued every session at
  the last adjusted close on or before it.

The runner re-checks the session date on every price it receives and refuses
any dated after the session it asked about (brief §9).
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from momentum25.domain.backtest.eligibility import is_eligible
from momentum25.domain.backtest.execution import (
    BACKTEST_METHOD_VERSION,
    ClosedOrder,
    ExecutionBar,
    ExecutionPolicy,
    Executor,
    Fill,
    Ledger,
    Order,
)
from momentum25.domain.backtest.momentum_signal import (
    MomentumSignal,
    compute_momentum_signal,
)
from momentum25.domain.backtest.portfolio_step import COST_BPS, plan_equal_weight_rebalance
from momentum25.domain.backtest.rebalance import rank_signals, select_portfolio
from momentum25.domain.errors import LookAheadError
from momentum25.domain.ports.trading_calendar import TradingCalendar
from momentum25.domain.ports.walk_forward import (
    BenchmarkProvider,
    EligibilityFactsProvider,
    PriceHistoryProvider,
    PricePoint,
)

_ZERO = Decimal(0)


@dataclass(frozen=True, slots=True)
class TradeRecord:
    """One fill in the trade log. ``quantity`` and ``notional`` are signed: + buy, - sell."""

    security_id: int
    side: str  # "BUY" or "SELL"
    quantity: Decimal
    fill_price: Decimal
    notional: Decimal
    fill_date: date
    cost: Decimal
    order_date: date
    delay_sessions: int
    partial: bool
    participation: Decimal | None


@dataclass(frozen=True, slots=True)
class RebalanceRecord:
    """Per-rebalance log line. ``trades`` are every fill the plan produced, deferred ones too."""

    decision_date: date
    fill_date: date
    universe_size: int
    eligible_count: int
    scored_count: int
    selected: tuple[int, ...]
    trades: tuple[TradeRecord, ...]
    total_cost: Decimal
    nav_pre_cost: Decimal
    stale_marks: int
    buy_scale: Decimal


@dataclass(frozen=True, slots=True)
class _Plan:
    """What one rebalance decided, before its fills are known."""

    decision_date: date
    fill_date: date
    universe_size: int
    eligible_count: int
    scored_count: int
    selected: tuple[int, ...]
    nav_pre: Decimal
    stale_marks: int
    buy_scale: Decimal


@dataclass(frozen=True, slots=True)
class NonTradingHolding:
    """A holding with no bar for more than the policy's flag window at the end date."""

    security_id: int
    last_bar_date: date
    sessions_without_bar: int
    value: Decimal
    weight: Decimal
    identity_status: str


@dataclass(frozen=True, slots=True)
class WalkForwardResult:
    """Full run output.

    ``total_return`` is reconstructed from the trade log, not read off any
    running total kept during the loop (addendum §3, item 14). The runner checks
    that the reconstruction equals its ledger.
    """

    rebalances: tuple[RebalanceRecord, ...]
    trades: tuple[TradeRecord, ...]
    initial_capital: Decimal
    final_nav: Decimal
    total_return: Decimal
    benchmark_return: Decimal | None
    # brief-addendum-approximations.md: any output surfacing benchmark_return
    # must carry this label next to the number (e.g. "Nifty 500 Price Index
    # (not TRI)"). ``None`` only when no benchmark provider was bound.
    benchmark_label: str | None
    method_version: int = BACKTEST_METHOD_VERSION
    execution_policy: dict[str, str | int | bool] | None = None
    cagr: Decimal | None = None
    max_drawdown: Decimal = _ZERO
    lower_bound_nav: Decimal | None = None
    closed_orders: tuple[ClosedOrder, ...] = ()
    nontrading_holdings: tuple[NonTradingHolding, ...] = ()


def format_walk_forward_report(result: WalkForwardResult) -> str:
    """Render a human-readable summary of ``result``.

    The benchmark return never appears without its label next to it
    (``brief-addendum-approximations.md``). ``benchmark_label`` is ``None``
    only when no benchmark provider was bound, and then the line is omitted.
    """
    lines = [
        f"Method: backtest v{result.method_version} (simulation; not investment performance)",
        f"Initial capital: {result.initial_capital}",
        f"Final NAV:       {result.final_nav}",
        f"Total return:    {result.total_return:.2%}",
    ]
    if result.cagr is not None:
        lines.append(f"CAGR:            {result.cagr:.2%}")
    lines.append(f"Max drawdown:    {result.max_drawdown:.2%}")
    if result.lower_bound_nav is not None and result.initial_capital:
        lower = result.lower_bound_nav / result.initial_capital - 1
        lines.append(f"Lower bound (non-trading holdings at zero): {lower:.2%}")
    if result.benchmark_return is not None:
        label = result.benchmark_label or "UNLABELED BENCHMARK"
        lines.append(f"Benchmark return ({label}): {result.benchmark_return:.2%}")
    lines.append(f"Rebalances: {len(result.rebalances)}, Trades: {len(result.trades)}")
    return "\n".join(lines)


def _months_before(d: date, months: int) -> date:
    """Return the calendar date ``months`` before ``d``, clamping the day.

    Day clamping handles month-length differences (e.g. 3 months before
    31-May is 28/29-Feb). The price provider then resolves this target to the
    latest actual session on or before it.
    """
    total = (d.year * 12 + (d.month - 1)) - months
    year, month = divmod(total, 12)
    month += 1
    next_month_first = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    last_day = (next_month_first - date.resolution).day
    return date(year, month, min(d.day, last_day))


class WalkForwardRunner:
    """Runs a monthly-rebalanced walk-forward backtest of the brief strategy."""

    def __init__(
        self,
        calendar: TradingCalendar,
        prices: PriceHistoryProvider,
        universe: EligibilityFactsProvider,
        benchmark: BenchmarkProvider | None = None,
        policy: ExecutionPolicy | None = None,
    ) -> None:
        """Bind the runner to a calendar, its point-in-time data providers and the policy."""
        self._calendar = calendar
        self._prices = prices
        self._universe = universe
        self._benchmark = benchmark
        self._policy = policy or ExecutionPolicy()

    def run(self, start: date, end: date, initial_capital: Decimal) -> WalkForwardResult:
        """Execute the backtest over ``[start, end]``.

        Raises ``ValueError`` if ``start`` is after ``end``. A reversed range
        would otherwise filter every session out and report a spurious
        zero-rebalance, zero-return run.
        """
        if start > end:
            raise ValueError("start must be on or before end")
        sessions = self._calendar.sessions_between(_months_before(start, 13), end)
        rebalance_dates = self._first_session_of_each_month(sessions, start, end)
        ledger = Ledger(cash=initial_capital)
        executor = Executor(ledger, self._policy)
        plans: list[_Plan] = []
        navs: list[Decimal] = []
        rebalance_set = set(rebalance_dates)

        for index, session in enumerate(sessions):
            if not rebalance_dates or session < rebalance_dates[0]:
                continue
            if session in rebalance_set and index > 0:
                plans.append(self._rebalance(sessions, index, executor, ledger))
            elif executor.pending:
                ids = {o.security_id for o in executor.pending}
                executor.work(session, index, self._bars(ids, session))
            navs.append(self._valuation(ledger, session))

        if rebalance_dates:
            executor.close_all_at_end(end)
        trades = tuple(_to_trade(f) for f in ledger.fills)
        final_nav = _reconstruct_nav_from_trades(list(trades), initial_capital, self._prices, end)
        ledger_nav = self._valuation(ledger, end)
        if final_nav != ledger_nav:  # the two paths are independent by construction
            raise AssertionError(f"trade-log NAV {final_nav} differs from ledger NAV {ledger_nav}")
        total_return = final_nav / initial_capital - 1 if initial_capital else _ZERO
        nontrading = self._nontrading(ledger, sessions, end, final_nav)
        lower = final_nav - sum((h.value for h in nontrading), _ZERO)
        return WalkForwardResult(
            rebalances=tuple(self._records(plans, trades)),
            trades=trades,
            initial_capital=initial_capital,
            final_nav=final_nav,
            total_return=total_return,
            benchmark_return=self._benchmark_return(rebalance_dates),
            benchmark_label=getattr(self._benchmark, "label", None),
            execution_policy=self._policy.as_dict(),
            cagr=_cagr(initial_capital, final_nav, rebalance_dates[0], end)
            if rebalance_dates
            else None,
            max_drawdown=_max_drawdown(navs),
            lower_bound_nav=lower,
            closed_orders=tuple(executor.closed),
            nontrading_holdings=nontrading,
        )

    # ── One rebalance ─────────────────────────────────────────────────────

    def _rebalance(
        self, sessions: list[date], index: int, executor: Executor, ledger: Ledger
    ) -> _Plan:
        fill_date, decision_date = sessions[index], sessions[index - 1]
        executor.supersede_all(fill_date)
        facts = self._universe.facts_as_of(decision_date)
        eligible_ids = [f.security_id for f in facts if is_eligible(f)]
        signals = self._score(eligible_ids, decision_date)
        target = select_portfolio(rank_signals(signals), frozenset(ledger.holdings))

        bars = self._bars(set(target) | set(ledger.holdings), fill_date)
        marks: dict[int, Decimal] = {}
        prices: dict[int, Decimal] = {}
        stale = 0
        for sid, shares in sorted(ledger.holdings.items()):
            bar = bars.get(sid)
            if bar is not None and bar.valid:
                price = bar.adj_open
            else:
                point = self._price_point(sid, decision_date, decision_date)
                price = point.adj_close if point is not None else _ZERO
                stale += 1
            prices[sid] = price
            marks[sid] = shares * price
        nav_pre = ledger.cash + sum((marks[sid] for sid in sorted(marks)), _ZERO)
        step = plan_equal_weight_rebalance(target, marks, nav_pre)

        window = self._policy.buy_window_sessions - 1
        sells: list[Order] = []
        buys: list[Order] = []
        for trade in step.trades:  # sorted by security_id
            if trade.notional < 0:
                held = ledger.holdings[trade.security_id]
                shares = (
                    held
                    if trade.security_id not in target
                    else -trade.notional / prices[trade.security_id]
                )
                sells.append(
                    Order(trade.security_id, "SELL", fill_date, index, None, shares=shares)
                )
            else:
                buys.append(
                    Order(
                        trade.security_id,
                        "BUY",
                        fill_date,
                        index,
                        index + window,
                        cash=trade.notional,
                    )
                )

        executor.submit(sells, [], fill_date, index, bars)
        need = sum((b.cash * (1 + COST_BPS) for b in buys), _ZERO)
        cash = ledger.cash
        if need == 0:
            scale = Decimal(1)
        elif cash > 0:
            scale = min(Decimal(1), cash / need)
        else:
            scale = _ZERO
        for b in buys:
            b.cash *= scale
        executor.submit([], buys, fill_date, index, bars)
        return _Plan(
            decision_date=decision_date,
            fill_date=fill_date,
            universe_size=len(facts),
            eligible_count=len(eligible_ids),
            scored_count=len(signals),
            selected=tuple(sorted(target)),
            nav_pre=nav_pre,
            stale_marks=stale,
            buy_scale=scale,
        )

    @staticmethod
    def _records(plans: list[_Plan], trades: tuple[TradeRecord, ...]) -> list[RebalanceRecord]:
        records = []
        for plan in plans:
            own = tuple(t for t in trades if t.order_date == plan.fill_date)
            records.append(
                RebalanceRecord(
                    decision_date=plan.decision_date,
                    fill_date=plan.fill_date,
                    universe_size=plan.universe_size,
                    eligible_count=plan.eligible_count,
                    scored_count=plan.scored_count,
                    selected=plan.selected,
                    trades=own,
                    total_cost=sum((t.cost for t in own), _ZERO),
                    nav_pre_cost=plan.nav_pre,
                    stale_marks=plan.stale_marks,
                    buy_scale=plan.buy_scale,
                )
            )
        return records

    # ── Signals and prices ────────────────────────────────────────────────

    def _score(self, security_ids: list[int], decision_date: date) -> list[MomentumSignal]:
        """Compute momentum signals using only prices dated <= decision_date.

        E1: a security without a valid bar dated ``decision_date`` is not
        scored; its last close would be an old price posing as ``price(t)``.
        A security missing any of its four required prices (t, 3m, 6m, 12m)
        is dropped too: fail closed, never a fabricated or forward-filled price.
        """
        signals: list[MomentumSignal] = []
        for sid in security_ids:
            bar = self._execution_bar(sid, decision_date)
            if bar is None or not bar.valid:
                continue
            p_3 = self._price(sid, _months_before(decision_date, 3), decision_date)
            p_6 = self._price(sid, _months_before(decision_date, 6), decision_date)
            p_12 = self._price(sid, _months_before(decision_date, 12), decision_date)
            if None in (p_3, p_6, p_12):
                continue
            signals.append(
                compute_momentum_signal(
                    security_id=sid,
                    price_t=bar.adj_close,
                    price_3m_ago=p_3,  # type: ignore[arg-type]
                    price_6m_ago=p_6,  # type: ignore[arg-type]
                    price_12m_ago=p_12,  # type: ignore[arg-type]
                )
            )
        return signals

    def _price(self, security_id: int, target: date, as_of: date) -> Decimal | None:
        """Fetch an adjusted close, enforcing the no-look-ahead contract."""
        point = self._price_point(security_id, target, as_of)
        return point.adj_close if point is not None else None

    def _price_point(self, security_id: int, target: date, as_of: date) -> PricePoint | None:
        """Fetch one adjusted bar and refuse any dated after ``as_of``.

        The runner does not trust the provider: checklist item 7 exercises
        this with a deliberately leaky provider.
        """
        point = self._prices.price_on_or_before(security_id, target, as_of)
        if point is None:
            return None
        if point.session_date > as_of:
            raise LookAheadError(
                f"price for security {security_id} dated {point.session_date} "
                f"is after decision date {as_of}"
            )
        return point

    def _execution_bar(self, security_id: int, session: date) -> ExecutionBar | None:
        """The bar dated exactly ``session``.

        A later bar is look-ahead and raises; an earlier one counts as no bar.
        """
        bar = self._prices.execution_bar(security_id, session)
        if bar is None:
            return None
        if bar.session_date > session:
            raise LookAheadError(
                f"execution bar for security {security_id} dated {bar.session_date} "
                f"is after session {session}"
            )
        return bar if bar.session_date == session else None

    def _bars(self, security_ids: set[int], session: date) -> dict[int, ExecutionBar]:
        bars = {}
        for sid in sorted(security_ids):
            bar = self._execution_bar(sid, session)
            if bar is not None:
                bars[sid] = bar
        return bars

    # ── Valuation ─────────────────────────────────────────────────────────

    def _valuation(self, ledger: Ledger, on: date) -> Decimal:
        """Cash plus every holding at its last adjusted close on or before ``on``.

        Sums in ``security_id`` order, as the trade-log replay does: Decimal
        rounding depends on order, and the two must agree exactly.
        """
        nav = ledger.cash
        for sid, shares in sorted(ledger.holdings.items()):
            point = self._price_point(sid, on, on)
            if point is not None:
                nav += shares * point.adj_close
        return nav

    def _nontrading(
        self, ledger: Ledger, sessions: list[date], end: date, nav: Decimal
    ) -> tuple[NonTradingHolding, ...]:
        end_index = bisect_right(sessions, end) - 1
        out = []
        for sid, shares in sorted(ledger.holdings.items()):
            point = self._price_point(sid, end, end)
            if point is None:
                continue
            gap = end_index - (bisect_right(sessions, point.session_date) - 1)
            if gap <= self._policy.nontrading_flag_sessions:
                continue
            value = shares * point.adj_close
            out.append(
                NonTradingHolding(
                    security_id=sid,
                    last_bar_date=point.session_date,
                    sessions_without_bar=gap,
                    value=value,
                    weight=value / nav if nav else _ZERO,
                    identity_status="no verified identity link",
                )
            )
        return tuple(out)

    def _benchmark_return(self, rebalance_dates: list[date]) -> Decimal | None:
        """Benchmark total return over the first-to-last rebalance span (reporting)."""
        if self._benchmark is None or len(rebalance_dates) < 2:
            return None
        first, last = rebalance_dates[0], rebalance_dates[-1]
        start_level = self._benchmark.level_on_or_before(first, first)
        end_level = self._benchmark.level_on_or_before(last, last)
        if start_level is None or end_level is None or start_level <= 0:
            return None
        return end_level / start_level - 1

    @staticmethod
    def _first_session_of_each_month(sessions: list[date], start: date, end: date) -> list[date]:
        """First trading session of each month within ``[start, end]``."""
        first_by_month: dict[tuple[int, int], date] = {}
        for d in sessions:
            if d < start or d > end:
                continue
            key = (d.year, d.month)
            if key not in first_by_month:
                first_by_month[key] = d
        return [first_by_month[k] for k in sorted(first_by_month)]


def _to_trade(fill: Fill) -> TradeRecord:
    signed = fill.quantity if fill.side == "BUY" else -fill.quantity
    return TradeRecord(
        security_id=fill.security_id,
        side=fill.side,
        quantity=signed,
        fill_price=fill.price,
        notional=fill.notional,
        fill_date=fill.fill_date,
        cost=fill.cost,
        order_date=fill.order_date,
        delay_sessions=fill.delay_sessions,
        partial=fill.partial,
        participation=fill.participation,
    )


def _max_drawdown(navs: list[Decimal]) -> Decimal:
    peak, worst = None, _ZERO
    for nav in navs:
        peak = nav if peak is None or nav > peak else peak
        if peak > 0:
            worst = min(worst, nav / peak - 1)
    return worst


def _cagr(initial: Decimal, final: Decimal, first: date, end: date) -> Decimal | None:
    days = (end - first).days
    if initial <= 0 or final <= 0 or days <= 0:
        return None
    return Decimal(str(float(final / initial) ** (365.25 / days) - 1))


def _reconstruct_nav_from_trades(
    trades: list[TradeRecord],
    initial_capital: Decimal,
    prices: PriceHistoryProvider,
    end: date,
) -> Decimal:
    """Recompute terminal NAV purely from the trade log (addendum §3, item 14).

    This deliberately ignores the runner's ledger. It replays cash and share
    quantities from the recorded fills, then marks the surviving positions at
    ``end``'s adjusted close. The runner raises if the two disagree.
    """
    cash = initial_capital
    qty: dict[int, Decimal] = {}
    for t in trades:  # in fill order
        cash -= t.notional
        cash -= t.cost
        qty[t.security_id] = qty.get(t.security_id, _ZERO) + t.quantity
    nav = cash
    for sid, held in sorted(qty.items()):
        if held == 0:
            continue
        point = prices.price_on_or_before(sid, end, end)
        if point is not None:
            nav += held * point.adj_close
    return nav
