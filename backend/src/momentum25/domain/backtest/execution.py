"""Order execution and the fill-driven ledger (brief addendum "Execution method v2").

Pure and deterministic. The runner (``application/use_cases/walk_forward.py``)
plans orders at each fill date and hands this module one session at a time.
Holdings and cash change only through fills. A fill is priced only from a
valid execution bar dated on the session it fills in; no price from any other
session is ever a fill price.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from momentum25.domain.backtest.portfolio_step import COST_BPS

BACKTEST_METHOD_VERSION = 2

# A remainder below these sizes is complete: Decimal division leaves dust.
_CASH_DUST = Decimal("1e-9")
_SHARE_DUST = Decimal("1e-12")
_ZERO = Decimal(0)


@dataclass(frozen=True, slots=True)
class ExecutionPolicy:
    """The approved execution constants (owner, 2026-10-20: S-1, S-2, S-3, S-6)."""

    buy_window_sessions: int = 5
    participation_cap: Decimal = Decimal("0.10")
    same_session_settlement: bool = True
    nontrading_flag_sessions: int = 20

    def as_dict(self) -> dict[str, str | int | bool]:
        """The policy as reported in every result."""
        return {
            "method_version": BACKTEST_METHOD_VERSION,
            "buy_window_sessions": self.buy_window_sessions,
            "participation_cap": str(self.participation_cap),
            "same_session_settlement": self.same_session_settlement,
            "nontrading_flag_sessions": self.nontrading_flag_sessions,
            "sell_retry": "every session until filled or superseded",
            "valuation": "last adjusted close on or before the date",
        }


@dataclass(frozen=True, slots=True)
class ExecutionBar:
    """One session's adjusted bar, as execution sees it."""

    session_date: date
    adj_open: Decimal
    adj_high: Decimal
    adj_low: Decimal
    adj_close: Decimal
    volume: int
    turnover_value: Decimal

    @property
    def valid(self) -> bool:
        """Tradable: a positive open inside the range, on positive volume."""
        return (
            self.adj_open > 0 and self.volume > 0 and self.adj_low <= self.adj_open <= self.adj_high
        )


@dataclass(slots=True)
class Order:
    """A live order. A buy carries cash; a sell carries shares."""

    security_id: int
    side: str  # "BUY" or "SELL"
    order_date: date
    placed_index: int
    expires_after_index: int | None  # None: no expiry (sells)
    cash: Decimal = _ZERO
    shares: Decimal = _ZERO


@dataclass(frozen=True, slots=True)
class Fill:
    """One execution. ``notional`` is signed: + buy, - sell."""

    security_id: int
    side: str
    quantity: Decimal  # positive shares
    price: Decimal
    notional: Decimal
    cost: Decimal
    order_date: date
    fill_date: date
    delay_sessions: int
    partial: bool
    participation: Decimal | None


@dataclass(frozen=True, slots=True)
class ClosedOrder:
    """An order that ended without filling in full."""

    security_id: int
    side: str
    order_date: date
    closed_on: date
    reason: str  # "expired", "superseded" or "open_at_end"
    remaining_cash: Decimal
    remaining_shares: Decimal


@dataclass(slots=True)
class Ledger:
    """Cash and holdings, changed only by :meth:`apply`."""

    cash: Decimal
    holdings: dict[int, Decimal] = field(default_factory=dict)
    fills: list[Fill] = field(default_factory=list)

    def apply(self, fill: Fill) -> None:
        """Book one fill: cash moves by notional, then cost; shares by quantity.

        The operation order matches the trade-log replay, so the two agree
        exactly. A sell never exceeds the shares held, and an exit sells exactly
        what is held, so a closed position reaches zero exactly.
        """
        self.cash -= fill.notional
        self.cash -= fill.cost
        delta = fill.quantity if fill.side == "BUY" else -fill.quantity
        held = self.holdings.get(fill.security_id, _ZERO) + delta
        if held < 0:
            raise ValueError(
                f"sell of {fill.quantity} exceeds holding of security {fill.security_id}"
            )
        if held == 0:
            self.holdings.pop(fill.security_id, None)
        else:
            self.holdings[fill.security_id] = held
        self.fills.append(fill)


class Executor:
    """Works live orders against one session's bars, sells before buys."""

    def __init__(self, ledger: Ledger, policy: ExecutionPolicy) -> None:
        """Bind the executor to a ledger and the policy."""
        self.ledger = ledger
        self.policy = policy
        self.pending: list[Order] = []
        self.closed: list[ClosedOrder] = []

    def supersede_all(self, on: date) -> None:
        """Close every live order: a new plan replaces them."""
        for order in self.pending:
            self._close(order, on, "superseded")
        self.pending = []

    def close_all_at_end(self, on: date) -> None:
        """Close every live order at the end of the window."""
        for order in self.pending:
            self._close(order, on, "open_at_end")
        self.pending = []

    def submit(
        self,
        sells: list[Order],
        buys: list[Order],
        session: date,
        index: int,
        bars: dict[int, ExecutionBar],
    ) -> None:
        """Execute a new plan's orders in their first session, keeping what does not fill."""
        for order in sells:
            if not self._execute(order, session, index, bars.get(order.security_id)):
                self.pending.append(order)
        for order in buys:
            if order.cash > 0 and not self._execute(
                order, session, index, bars.get(order.security_id)
            ):
                self.pending.append(order)

    def work(self, session: date, index: int, bars: dict[int, ExecutionBar]) -> None:
        """Retry live orders on a later session: sells first, then buys, by security."""
        keep: list[Order] = []
        for order in sorted(self.pending, key=lambda o: (o.side != "SELL", o.security_id)):
            if order.expires_after_index is not None and index > order.expires_after_index:
                self._close(order, session, "expired")
                continue
            if not self._execute(order, session, index, bars.get(order.security_id)):
                keep.append(order)
        self.pending = keep

    def _execute(self, order: Order, session: date, index: int, bar: ExecutionBar | None) -> bool:
        """Fill what the session allows; return True when the order is complete."""
        if bar is None or bar.session_date != session or not bar.valid:
            return False
        price, cap = bar.adj_open, self.policy.participation_cap
        limit = cap * bar.turnover_value if bar.turnover_value > 0 else _ZERO
        if order.side == "SELL":
            shares = min(order.shares, self.ledger.holdings.get(order.security_id, _ZERO))
            if shares <= 0:
                return True
            shares = min(shares, limit / price)
            if shares <= 0:
                return False
            notional = -(shares * price)
            order.shares -= shares
            done = order.shares <= _SHARE_DUST
        else:
            notional = min(order.cash, limit)
            cash = self.ledger.cash
            notional = min(notional, cash / (1 + COST_BPS)) if cash > 0 else _ZERO
            if notional <= 0:
                return False
            shares = notional / price
            order.cash -= notional
            done = order.cash <= _CASH_DUST
        self.ledger.apply(
            Fill(
                security_id=order.security_id,
                side=order.side,
                quantity=shares,
                price=price,
                notional=notional,
                cost=abs(notional) * COST_BPS,
                order_date=order.order_date,
                fill_date=session,
                delay_sessions=index - order.placed_index,
                partial=not done,
                participation=abs(notional) / bar.turnover_value
                if bar.turnover_value > 0
                else None,
            )
        )
        return done

    def _close(self, order: Order, on: date, reason: str) -> None:
        self.closed.append(
            ClosedOrder(
                security_id=order.security_id,
                side=order.side,
                order_date=order.order_date,
                closed_on=on,
                reason=reason,
                remaining_cash=order.cash,
                remaining_shares=order.shares,
            )
        )
