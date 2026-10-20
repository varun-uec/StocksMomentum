"""Independent reference for backtest method v2 (brief-addendum-execution-v2.md).

Written from the brief and the addendum, not from the production code, and it
imports nothing from ``momentum25``. The production runner must agree with it
fill for fill (``tests/unit/test_walk_forward_reference_agreement.py``).

Inputs are plain data:
    bars:      {security_id: [(date, open, high, low, close, volume, adj_factor, turnover)]},
               ascending by date
    universe:  [(security_id, exchange, isin, listing_date, delisting_date), ...] in id order
    sessions:  every exchange session from 13 months before ``start`` to ``end``
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

COST = Decimal("30") / Decimal("10000")
N, BUFFER = 30, 45
THIRD = Decimal(1) / Decimal(3)
ZERO = Decimal(0)
BUY_WINDOW = 5
CAP = Decimal("0.10")
FLAG_SESSIONS = 20


def months_before(d: date, m: int) -> date:
    t = d.year * 12 + d.month - 1 - m
    y, mo = divmod(t, 12)
    mo += 1
    nxt = date(y + 1, 1, 1) if mo == 12 else date(y, mo + 1, 1)
    return date(y, mo, min(d.day, (nxt - timedelta(days=1)).day))


@dataclass
class Bar:
    day: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    turnover: Decimal

    @property
    def tradable(self) -> bool:
        return self.open > 0 and self.volume > 0 and self.low <= self.open <= self.high


class Market:
    def __init__(self, bars: dict[int, list[tuple]]) -> None:
        self.days: dict[int, list[date]] = {}
        self.rows: dict[int, list[Bar]] = {}
        for sid, rows in bars.items():
            self.days[sid] = [r[0] for r in rows]
            self.rows[sid] = [
                Bar(d, o * f, h * f, lo * f, c * f, v, t) for (d, o, h, lo, c, v, f, t) in rows
            ]

    def on(self, sid: int, day: date) -> Bar | None:
        days = self.days.get(sid, [])
        i = bisect_right(days, day) - 1
        return self.rows[sid][i] if i >= 0 and days[i] == day else None

    def last(self, sid: int, day: date) -> Bar | None:
        days = self.days.get(sid, [])
        i = bisect_right(days, day) - 1
        return self.rows[sid][i] if i >= 0 else None


@dataclass
class LiveOrder:
    sid: int
    side: str
    placed: int
    expires: int | None
    order_date: date
    cash: Decimal = ZERO
    shares: Decimal = ZERO


@dataclass
class Outcome:
    fills: list[tuple] = field(
        default_factory=list
    )  # (sid, side, fill_date, price, shares, notional, cost)
    closed: list[tuple] = field(default_factory=list)  # (sid, side, order_date, reason)
    navs: list[Decimal] = field(default_factory=list)
    selected: list[tuple[int, ...]] = field(default_factory=list)
    final_nav: Decimal = ZERO
    holdings: dict[int, Decimal] = field(default_factory=dict)


def run(bars, universe, sessions, start: date, end: date, capital: Decimal) -> Outcome:
    mkt = Market(bars)
    out = Outcome()
    cash, held = capital, {}
    pending: list[LiveOrder] = []
    firsts: dict[tuple[int, int], date] = {}
    for d in sessions:
        if start <= d <= end:
            firsts.setdefault((d.year, d.month), d)
    fill_days = set(firsts.values())
    first_fill = min(fill_days)

    def fill(o: LiveOrder, day: date, idx: int) -> bool:
        nonlocal cash
        bar = mkt.on(o.sid, day)
        if bar is None or not bar.tradable:
            return False
        limit = CAP * bar.turnover if bar.turnover > 0 else ZERO
        if o.side == "SELL":
            q = min(o.shares, held.get(o.sid, ZERO))
            if q <= 0:
                return True
            q = min(q, limit / bar.open)
            if q <= 0:
                return False
            notional = -(q * bar.open)
            o.shares -= q
            done = o.shares <= Decimal("1e-12")
        else:
            notional = min(o.cash, limit)
            notional = min(notional, cash / (1 + COST)) if cash > 0 else ZERO
            if notional <= 0:
                return False
            q = notional / bar.open
            o.cash -= notional
            done = o.cash <= Decimal("1e-9")
        cost = abs(notional) * COST
        cash -= notional
        cash -= cost
        new = held.get(o.sid, ZERO) + (q if o.side == "BUY" else -q)
        if new == 0:
            held.pop(o.sid, None)
        else:
            held[o.sid] = new
        out.fills.append((o.sid, o.side, day, bar.open, q, notional, cost))
        return done

    for idx, day in enumerate(sessions):
        if day < first_fill or day > end:
            continue
        if day in fill_days:
            decision = sessions[idx - 1]
            for o in pending:
                out.closed.append((o.sid, o.side, o.order_date, "superseded"))
            pending = []
            # signal
            signals = []
            for sid, exchange, isin, listed, delisted in universe:
                if exchange not in ("NSE", "BOTH") or (isin or "").upper().startswith("INF"):
                    continue
                if (
                    listed is None
                    or listed > decision
                    or (delisted is not None and delisted <= decision)
                ):
                    continue
                if (decision - listed).days < 252:
                    continue
                today = mkt.on(sid, decision)
                if today is None or not today.tradable:
                    continue
                past = [mkt.last(sid, months_before(decision, m)) for m in (3, 6, 12)]
                if any(p is None for p in past):
                    continue
                r3, r6, r12 = (today.close / p.close - 1 for p in past)  # type: ignore[union-attr]
                signals.append((THIRD * r3 + THIRD * r6 + THIRD * r12, r12, r6, r3, sid))
            ranked = sorted(signals, key=lambda s: (-s[0], -s[1], -s[2], -s[3]))
            rank = {s[4]: i for i, s in enumerate(ranked, 1)}
            kept = {sid for sid in held if rank.get(sid, BUFFER + 1) <= BUFFER}
            adds = [s[4] for s in ranked[:N] if s[4] not in kept][: max(N - len(kept), 0)]
            target = kept | set(adds)
            out.selected.append(tuple(sorted(target)))
            # marks and plan
            price, value = {}, {}
            for sid, q in sorted(held.items()):
                bar = mkt.on(sid, day)
                if bar is not None and bar.tradable:
                    price[sid] = bar.open
                else:
                    last = mkt.last(sid, decision)
                    price[sid] = last.close if last is not None else ZERO
                value[sid] = q * price[sid]
            nav = cash + sum((value[sid] for sid in sorted(value)), ZERO)
            per_name = nav / Decimal(len(target)) if target else ZERO
            sells, buys = [], []
            for sid in sorted(target | set(held)):
                delta = (per_name if sid in target else ZERO) - value.get(sid, ZERO)
                if delta == 0:
                    continue
                if delta < 0:
                    shares = held[sid] if sid not in target else -delta / price[sid]
                    sells.append(LiveOrder(sid, "SELL", idx, None, day, shares=shares))
                else:
                    buys.append(LiveOrder(sid, "BUY", idx, idx + BUY_WINDOW - 1, day, cash=delta))
            for o in sells:
                if not fill(o, day, idx):
                    pending.append(o)
            need = sum((b.cash * (1 + COST) for b in buys), ZERO)
            if need == 0:
                scale = Decimal(1)
            elif cash > 0:
                scale = min(Decimal(1), cash / need)
            else:
                scale = ZERO
            for b in buys:
                b.cash *= scale
                if b.cash > 0 and not fill(b, day, idx):
                    pending.append(b)
        else:
            keep = []
            for o in sorted(pending, key=lambda o: (o.side != "SELL", o.sid)):
                if o.expires is not None and idx > o.expires:
                    out.closed.append((o.sid, o.side, o.order_date, "expired"))
                    continue
                if not fill(o, day, idx):
                    keep.append(o)
            pending = keep
        navs = cash
        for sid, q in sorted(held.items()):
            bar = mkt.last(sid, day)
            if bar is not None:
                navs += q * bar.close
        out.navs.append(navs)
    for o in pending:
        out.closed.append((o.sid, o.side, o.order_date, "open_at_end"))
    nav = cash
    for sid, q in sorted(held.items()):
        bar = mkt.last(sid, end)
        if bar is not None:
            nav += q * bar.close
    out.final_nav = nav
    out.holdings = dict(held)
    return out
