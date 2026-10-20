"""Stage A reference simulator: one parameterised execution-driven ledger.

Independent of momentum25 backtest/domain code (as sim.py). Parameters:

  price_source  "adj_close": production rule (rows with NULL adj_close dropped)
                "computed" : open/close x adj_factor for every row
  universe      exchanges tuple, equity_only flag
  require_decision_bar  E1: score only names with a valid bar on D
  buy_window    sessions after F a buy may wait (0 = F only, None = until next decision)
  sell_retry    True: an unfilled sell retries each later session until superseded
  cap           None, or max fill as a fraction of the session's traded value
                (partial fills; the remainder waits under the same window rules)
  t1_settlement True: sell proceeds become available the next session

A valid execution bar: open > 0, volume > 0, low <= open <= high.
Ledger: holdings and cash change only through fills; no leverage.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

COST = Decimal("30") / Decimal("10000")
N, BUF = 30, 45
W = Decimal(1) / Decimal(3)
ZERO = Decimal(0)


def months_before(d: date, m: int) -> date:
    t = d.year * 12 + d.month - 1 - m
    y, mo = divmod(t, 12)
    mo += 1
    nxt = date(y + 1, 1, 1) if mo == 12 else date(y, mo + 1, 1)
    return date(y, mo, min(d.day, (nxt - timedelta(days=1)).day))


class Px:
    def __init__(self, bars, start, end, price_source="computed"):
        self.s = {}
        for sid, rows in bars.items():
            for (dt, o, h, l, c, v, f, ac, tv) in rows:
                if not (start <= dt <= end):
                    continue
                if price_source == "adj_close":
                    if ac is None:
                        continue
                    close = ac
                else:
                    close = c * f
                valid = o > 0 and (v or 0) > 0 and l <= o <= h
                L = self.s.setdefault(sid, ([], [], [], [], []))
                L[0].append(dt); L[1].append(o * f); L[2].append(close); L[3].append(tv or ZERO); L[4].append(valid)
        self.idx = {sid: {d: i for i, d in enumerate(v[0])} for sid, v in self.s.items()}

    def close_le(self, sid, d):
        v = self.s.get(sid)
        if not v:
            return None, None
        i = bisect_right(v[0], d) - 1
        return (v[0][i], v[2][i]) if i >= 0 else (None, None)

    def has(self, sid, d):
        return d in self.idx.get(sid, {})

    def exec_bar(self, sid, d):
        """(adj_open, traded_value) if a valid execution bar exists on d."""
        i = self.idx.get(sid, {}).get(d)
        if i is None:
            return None
        v = self.s[sid]
        return (v[1][i], v[3][i]) if v[4][i] else None


@dataclass
class Fill:
    sid: int
    side: str
    qty: Decimal
    price: Decimal
    notional: Decimal
    cost: Decimal
    order_date: date
    fill_date: date
    delay: int
    partial: bool
    participation: Decimal | None


@dataclass
class Order:
    sid: int
    side: str
    cash: Decimal = ZERO
    qty: Decimal = ZERO
    placed: int = 0
    expire: int = 10**9
    order_date: date = None


@dataclass
class Out:
    fills: list = field(default_factory=list)
    orders: list = field(default_factory=list)  # (F, sid, side, planned |notional|, has exec bar on F)
    cancelled: list = field(default_factory=list)  # (order, remaining notional or shares, reason)
    rebal: list = field(default_factory=list)
    daily: list = field(default_factory=list)
    final_nav: Decimal = ZERO
    end_pending: list = field(default_factory=list)
    min_cash: Decimal = Decimal(10**18)


def run(px, universe_rows, sessions, start, end, cap0, *, require_decision_bar=True,
        buy_window=0, sell_retry=True, cap=None, t1_settlement=False):
    sidx = {d: i for i, d in enumerate(sessions)}
    firsts = {}
    for d in sessions:
        if start <= d <= end:
            firsts.setdefault((d.year, d.month), d)
    fill_dates = [firsts[k] for k in sorted(firsts)]
    o = Out()
    cash, qty = cap0, {}
    unsettled = ZERO  # T+1 sell proceeds
    pending: list[Order] = []

    def execute(od, d, i):
        nonlocal cash, unsettled
        eb = px.exec_bar(od.sid, d)
        if eb is None:
            return False
        p, tv = eb
        if od.side == "SELL":
            q = min(od.qty, qty.get(od.sid, ZERO))
            if q <= 0:
                return True
            if cap is not None:
                q = min(q, cap * tv / p) if tv > 0 else ZERO
            if q <= 0:
                return False
            notional = -(q * p)
            od.qty -= q
            done = od.qty <= Decimal("1e-12")
        else:
            notional = od.cash
            if cap is not None:
                notional = min(notional, cap * tv) if tv > 0 else ZERO
            avail = cash
            notional = min(notional, avail / (1 + COST)) if avail > 0 else ZERO
            if notional <= 0:
                return False
            q = notional / p
            od.cash -= notional
            done = od.cash <= Decimal("1e-9")
        c = abs(notional) * COST
        if od.side == "SELL" and t1_settlement:
            unsettled += -notional - c  # cost is netted from the proceeds
        else:
            cash -= notional + c
        qty[od.sid] = qty.get(od.sid, ZERO) + (q if od.side == "BUY" else -q)
        if qty[od.sid] <= Decimal("1e-12"):
            del qty[od.sid]
        o.fills.append(Fill(od.sid, od.side, q, p, notional, c, od.order_date, d, i - od.placed,
                            not done, abs(notional) / tv if tv > 0 else None))
        o.min_cash = min(o.min_cash, cash)
        return done

    def work(d, i):
        nonlocal pending
        keep = []
        for od in sorted(pending, key=lambda x: (x.side != "SELL", x.sid)):
            if i > od.expire:
                o.cancelled.append((od, od.cash if od.side == "BUY" else od.qty, "expired"))
                continue
            if not execute(od, d, i):
                keep.append(od)
        pending = keep

    nf = 0
    for d in sessions:
        if d < fill_dates[0] or d > end:
            continue
        i = sidx[d]
        if t1_settlement and unsettled:
            cash += unsettled
            unsettled = ZERO
        if nf < len(fill_dates) and d == fill_dates[nf]:
            F, D = d, sessions[i - 1]
            nf += 1
            for od in pending:  # the new plan supersedes every pending order
                o.cancelled.append((od, od.cash if od.side == "BUY" else od.qty, "superseded"))
            pending = []
            sigs = []
            for sid, listed, gone in universe_rows:
                if listed > D or (gone is not None and D >= gone) or (D - listed).days < 252:
                    continue
                if require_decision_bar and not px.has(sid, D):
                    continue
                pt = px.close_le(sid, D)[1]
                p3 = px.close_le(sid, months_before(D, 3))[1]
                p6 = px.close_le(sid, months_before(D, 6))[1]
                p12 = px.close_le(sid, months_before(D, 12))[1]
                if None in (pt, p3, p6, p12) or min(pt, p3, p6, p12) <= 0:
                    continue
                r3, r6, r12 = pt / p3 - 1, pt / p6 - 1, pt / p12 - 1
                sigs.append((W * r3 + W * r6 + W * r12, r12, r6, r3, sid))
            ranked = sorted(sigs, key=lambda s: (-s[0], -s[1], -s[2], -s[3]))
            rank = {s[4]: k for k, s in enumerate(ranked, 1)}
            kept = {s for s in qty if rank.get(s, BUF + 1) <= BUF}
            adds = [s[4] for s in ranked[:N] if s[4] not in kept][: max(N - len(kept), 0)]
            target = frozenset(kept | set(adds))
            marks, stale = {}, 0
            for sid, q in qty.items():
                eb = px.exec_bar(sid, F)
                p = eb[0] if eb else px.close_le(sid, D)[1]
                stale += eb is None
                marks[sid] = q * p
            nav_pre = cash + unsettled + sum(marks.values())
            tv_ = nav_pre / len(target) if target else ZERO
            sells, buys = [], []
            for sid in sorted(set(target) | set(qty)):
                delta = (tv_ if sid in target else ZERO) - marks.get(sid, ZERO)
                if delta == 0:
                    continue
                o.orders.append((F, sid, "BUY" if delta > 0 else "SELL", abs(delta), px.exec_bar(sid, F) is not None))
                if delta < 0:
                    sq = qty[sid] if sid not in target else (-delta) / (marks[sid] / qty[sid])
                    sells.append(Order(sid, "SELL", qty=sq, placed=i, order_date=F,
                                       expire=10**9 if sell_retry else i))
                else:
                    buys.append(Order(sid, "BUY", cash=delta, placed=i, order_date=F,
                                      expire=i + (10**9 if buy_window is None else buy_window)))
            for od in sells:
                if not execute(od, F, i):
                    pending.append(od)
            need = sum((b.cash * (1 + COST) for b in buys), ZERO)
            budget = cash + unsettled  # T+1: proceeds due next session fund buys that wait for them
            scale = min(Decimal(1), budget / need) if need > 0 and budget > 0 else (Decimal(1) if need == 0 else ZERO)
            for b in buys:
                b.cash *= scale
                if b.cash > 0 and not execute(b, F, i):
                    pending.append(b)
            o.rebal.append(dict(F=F, D=D, nav_pre=nav_pre, target=sorted(target), scored=len(ranked),
                                stale_marks=stale, scale=scale, sell_need=need - cash if need > cash else ZERO))
        else:
            work(d, i)
        nav, stale_val, vals = cash + unsettled, ZERO, []
        for sid, q in qty.items():
            bd, c = px.close_le(sid, d)
            nav += q * c
            vals.append(q * c)
            if bd is None or (sidx.get(bd) is not None and i - sidx[bd] > 20):
                stale_val += q * c
        o.daily.append((d, nav, stale_val, cash, len(vals), max(vals, default=ZERO)))
    o.end_pending = pending
    o.final_nav = cash + unsettled + sum((q * px.close_le(s, end)[1] for s, q in qty.items()), ZERO)
    o.qty = qty
    return o
