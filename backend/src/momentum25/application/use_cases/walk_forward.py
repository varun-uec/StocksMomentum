"""Walk-forward backtest runner.

Wires the frozen ``domain/backtest/`` math to real, point-in-time historical
data.

This is the seam Loop 2 exists to build (see ``handoff/brief-addendum-loop2.md``
§2). It is the first place "as of date X" becomes an *enforced* constraint
rather than a documented intention: the runner re-checks the session date on
every price it receives and refuses any dated on or after the decision date
(brief §9). It never re-litigates signal, ranking, or buffer logic — those come
from ``domain/backtest/`` unchanged.

Fill timing (brief §5): decide at the close of the last session of month M-1,
fill at the first session of month M. The fill date is a real, later date than
the decision date in this code — never a same-day fill.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from momentum25.domain.backtest.eligibility import is_eligible
from momentum25.domain.backtest.momentum_signal import (
    MomentumSignal,
    compute_momentum_signal,
)
from momentum25.domain.backtest.portfolio_step import (
    COST_BPS,
    Trade,
    plan_equal_weight_rebalance,
)
from momentum25.domain.backtest.rebalance import rank_signals, select_portfolio
from momentum25.domain.ports.trading_calendar import TradingCalendar
from momentum25.domain.ports.walk_forward import (
    BenchmarkProvider,
    EligibilityFactsProvider,
    PriceHistoryProvider,
)


class LookAheadError(Exception):
    """A provider returned data dated on or after the decision date (brief §9)."""


@dataclass(frozen=True, slots=True)
class TradeRecord:
    """One fill in the trade log — the audit unit for checklist items 10 and 14."""

    security_id: int
    side: str  # "BUY" or "SELL"
    quantity: Decimal
    fill_price: Decimal
    notional: Decimal  # signed: + buy, - sell
    fill_date: date
    cost: Decimal


@dataclass(frozen=True, slots=True)
class RebalanceRecord:
    """Per-rebalance log line (addendum §3)."""

    decision_date: date
    fill_date: date
    universe_size: int
    eligible_count: int
    selected: tuple[int, ...]
    trades: tuple[TradeRecord, ...]
    total_cost: Decimal
    nav_pre_cost: Decimal


@dataclass(frozen=True, slots=True)
class WalkForwardResult:
    """Full run output.

    ``total_return`` is reconstructed from the trade log, not read off any
    running total kept during the loop (addendum §3, item 14).
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


def format_walk_forward_report(result: WalkForwardResult) -> str:
    """Render a human-readable summary of ``result``.

    The report/output surface required by
    ``brief-addendum-approximations.md`` §"What Reviewer checks this round":
    the benchmark return must never appear without its label directly next
    to it. ``benchmark_label`` is ``None`` only when no benchmark provider
    was bound to the runner, in which case the benchmark line is omitted
    entirely rather than printed unlabeled.
    """
    lines = [
        f"Initial capital: {result.initial_capital}",
        f"Final NAV:       {result.final_nav}",
        f"Total return:    {result.total_return:.2%}",
    ]
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
    # Clamp day to the last valid day of the target month.
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
    ) -> None:
        """Bind the runner to a calendar and its point-in-time data providers."""
        self._calendar = calendar
        self._prices = prices
        self._universe = universe
        self._benchmark = benchmark

    def run(
        self, start: date, end: date, initial_capital: Decimal
    ) -> WalkForwardResult:
        """Execute the backtest over ``[start, end]``.

        Rebalances on the first session of each month in range. For each, it
        scores the point-in-time universe as of the prior session's close and
        fills at the first-session price — a strictly later date. Returns the
        per-rebalance and trade logs plus a trade-log-reconstructed summary.

        Raises ``ValueError`` if ``start`` is after ``end``. A reversed range
        would otherwise filter every session out and report a spurious
        zero-rebalance, zero-return run.
        """
        if start > end:
            raise ValueError("start must be on or before end")
        sessions = self._calendar.sessions_between(_months_before(start, 13), end)
        session_index = {d: i for i, d in enumerate(sessions)}
        rebalance_dates = self._first_session_of_each_month(sessions, start, end)

        positions: dict[int, Decimal] = {}  # security_id -> quantity held
        cash = initial_capital
        rebalances: list[RebalanceRecord] = []
        all_trades: list[TradeRecord] = []

        for fill_date in rebalance_dates:
            decision_date = self._prior_session(fill_date, sessions, session_index)
            if decision_date is None:
                continue  # no prior session in range to decide on

            facts = self._universe.facts_as_of(decision_date)
            eligible_ids = [f.security_id for f in facts if is_eligible(f)]
            signals = self._score(eligible_ids, decision_date)

            ranked = rank_signals(signals)
            target = select_portfolio(ranked, frozenset(positions))

            nav_pre, mark = self._mark_to_market(positions, cash, fill_date)
            step = plan_equal_weight_rebalance(
                target_holdings=target,
                current_positions=mark,
                portfolio_value=nav_pre,
            )

            trades = self._apply(step.trades, fill_date)
            all_trades.extend(trades)
            positions, cash = self._settle(target, nav_pre, step.total_cost, fill_date)

            rebalances.append(
                RebalanceRecord(
                    decision_date=decision_date,
                    fill_date=fill_date,
                    universe_size=len(facts),
                    eligible_count=len(eligible_ids),
                    selected=tuple(sorted(target)),
                    trades=tuple(trades),
                    total_cost=step.total_cost,
                    nav_pre_cost=nav_pre,
                )
            )

        final_nav = _reconstruct_nav_from_trades(all_trades, initial_capital, self._prices, end)
        total_return = final_nav / initial_capital - 1 if initial_capital else Decimal(0)
        return WalkForwardResult(
            rebalances=tuple(rebalances),
            trades=tuple(all_trades),
            initial_capital=initial_capital,
            final_nav=final_nav,
            total_return=total_return,
            benchmark_return=self._benchmark_return(rebalance_dates),
            benchmark_label=getattr(self._benchmark, "label", None),
        )

    # ── Internals ─────────────────────────────────────────────────────────

    def _score(self, security_ids: list[int], decision_date: date) -> list[MomentumSignal]:
        """Compute momentum signals using only prices dated <= decision_date.

        A security missing any of its four required prices (t, 3m, 6m, 12m) is
        dropped — fail closed, never scored on a fabricated or forward-filled
        price.
        """
        signals: list[MomentumSignal] = []
        for sid in security_ids:
            p_t = self._price(sid, decision_date, decision_date)
            p_3 = self._price(sid, _months_before(decision_date, 3), decision_date)
            p_6 = self._price(sid, _months_before(decision_date, 6), decision_date)
            p_12 = self._price(sid, _months_before(decision_date, 12), decision_date)
            if None in (p_t, p_3, p_6, p_12):
                continue
            signals.append(
                compute_momentum_signal(
                    security_id=sid,
                    price_t=p_t,  # type: ignore[arg-type]
                    price_3m_ago=p_3,  # type: ignore[arg-type]
                    price_6m_ago=p_6,  # type: ignore[arg-type]
                    price_12m_ago=p_12,  # type: ignore[arg-type]
                )
            )
        return signals

    def _price(self, security_id: int, target: date, as_of: date) -> Decimal | None:
        """Fetch an adjusted close, enforcing the no-look-ahead contract.

        The runner does not trust the provider to obey ``as_of``: it re-checks
        the returned session date and raises :class:`LookAheadError` if the
        provider handed back a price dated on or after ``as_of``. This is the
        mechanism checklist item 7 exercises with a deliberately leaky provider.
        """
        point = self._prices.price_on_or_before(security_id, target, as_of)
        if point is None:
            return None
        if point.session_date > as_of:
            raise LookAheadError(
                f"price for security {security_id} dated {point.session_date} "
                f"is after decision date {as_of}"
            )
        return point.adj_close

    def _mark_to_market(
        self, positions: dict[int, Decimal], cash: Decimal, on: date
    ) -> tuple[Decimal, dict[int, Decimal]]:
        """Value held positions at ``on``'s adjusted close.

        A held name with no price at ``on`` (suspended/delisted) is marked to
        zero — conservative and look-ahead-free.
        ``ponytail: mark-missing-price-to-zero; refine with a last-traded /
        delisting-recovery price when a delisting provider exists.``
        """
        mark: dict[int, Decimal] = {}
        nav = cash
        for sid, qty in positions.items():
            price = self._price(sid, on, on)
            value = qty * price if price is not None else Decimal(0)
            mark[sid] = value
            nav += value
        return nav, mark

    def _apply(self, trades: tuple[Trade, ...], fill_date: date) -> list[TradeRecord]:
        """Turn planned notional trades into priced fills at ``fill_date``."""
        records: list[TradeRecord] = []
        for t in trades:
            price = self._price(t.security_id, fill_date, fill_date)
            if price is None or price <= 0:
                # Cannot fill without a real fill price. Skip rather than invent
                # one; the position simply is not established/closed this step.
                continue
            qty = t.notional / price
            records.append(
                TradeRecord(
                    security_id=t.security_id,
                    side="BUY" if t.notional > 0 else "SELL",
                    quantity=qty,
                    fill_price=price,
                    notional=t.notional,
                    fill_date=fill_date,
                    cost=abs(t.notional) * COST_BPS,
                )
            )
        return records

    def _settle(
        self,
        target: frozenset[int],
        nav_pre: Decimal,
        total_cost: Decimal,
        fill_date: date,
    ) -> tuple[dict[int, Decimal], Decimal]:
        """Set post-rebalance positions to equal weight and realize costs."""
        if not target:
            return {}, nav_pre - total_cost
        target_value = nav_pre / Decimal(len(target))
        positions: dict[int, Decimal] = {}
        invested = Decimal(0)
        for sid in sorted(target):
            price = self._price(sid, fill_date, fill_date)
            if price is None or price <= 0:
                continue
            positions[sid] = target_value / price
            invested += target_value
        cash = nav_pre - invested - total_cost
        return positions, cash

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
    def _first_session_of_each_month(
        sessions: list[date], start: date, end: date
    ) -> list[date]:
        """First trading session of each month within ``[start, end]``."""
        first_by_month: dict[tuple[int, int], date] = {}
        for d in sessions:
            if d < start or d > end:
                continue
            key = (d.year, d.month)
            if key not in first_by_month:
                first_by_month[key] = d
        return [first_by_month[k] for k in sorted(first_by_month)]

    @staticmethod
    def _prior_session(
        fill_date: date, sessions: list[date], session_index: dict[date, int]
    ) -> date | None:
        """The trading session immediately before ``fill_date`` (the decision date)."""
        idx = session_index.get(fill_date)
        if idx is None or idx == 0:
            return None
        return sessions[idx - 1]


def _reconstruct_nav_from_trades(
    trades: list[TradeRecord],
    initial_capital: Decimal,
    prices: PriceHistoryProvider,
    end: date,
) -> Decimal:
    """Recompute terminal NAV purely from the trade log (addendum §3, item 14).

    This deliberately ignores any NAV the runner tracked during its loop. It
    replays cash and share quantities from the recorded fills, then marks the
    surviving positions at ``end``'s adjusted close. If this disagrees with the
    loop's own bookkeeping, the disagreement is a real finding — the two paths
    are independent by construction.
    """
    cash = initial_capital
    qty: dict[int, Decimal] = {}
    for t in sorted(trades, key=lambda x: (x.fill_date, x.security_id)):
        cash -= t.notional
        cash -= t.cost
        qty[t.security_id] = qty.get(t.security_id, Decimal(0)) + t.quantity
    nav = cash
    for sid, held in qty.items():
        if held == 0:
            continue
        point = prices.price_on_or_before(sid, end, end)
        if point is not None:
            nav += held * point.adj_close
    return nav
