"""Independent reference simulator for the brief strategy under several fill policies.

Imports no momentum25 backtest/domain code. Signal (brief §2), ranking and
tie-break (§3), buffer (§6), equal weight (§4), 30 bps cost (§7), fill timing
(§5) are re-implemented from brief.md. Market data and the NSE session list
come from the read-only export and the production calendar (data, not logic).

Policies
  P0  current engine: mark and fill at adj_open of the last bar <= fill date;
      positions reset to target (replicates walk_forward.py exactly).
  A   strict same session: fill only at adj_open of a bar ON the fill date;
      unfilled buy -> cash, unfilled sell -> keep position.
  C5  cancel after window: like B but an order expires after 5 sessions.
  B   next eligible session: unfilled orders fill at adj_open of the first
      later session with a bar; expire at the next rebalance.
  D   hybrid: buys as A (same session or cancel); sells as B but never expire
      (re-issued at each rebalance until filled).

Every non-P0 policy: orders planned against marks at the fill-date open
(adj_open if a bar exists that day, else last adj_close <= decision date);
buys are cash amounts, sells are share counts; sells settle before buys;
buys are scaled pro rata if cash (after costs) is short. No leverage.
"""
from __future__ import annotations

import json
import sys
from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

import load
from momentum25.infrastructure.calendar.nse_calendar import get_nse_trading_calendar

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
    def __init__(self, bars, start, end):
        self.s = {}
        for sid, rows in bars.items():
            for (dt, o, _h, _l, _c, v, f, ac, _t) in rows:
                if start <= dt <= end and ac is not None:
                    ds, os_, cs, vs = self.s.setdefault(sid, ([], [], [], []))
                    ds.append(dt); os_.append(o * f); cs.append(ac); vs.append(v)
        self.dset = {sid: set(v[0]) for sid, v in self.s.items()}

    def _idx(self, sid, d):
        v = self.s.get(sid)
        if not v:
            return None, None
        i = bisect_right(v[0], d) - 1
        return (v, i) if i >= 0 else (None, None)

    def close_le(self, sid, d):
        v, i = self._idx(sid, d)
        return (v[0][i], v[2][i]) if v else (None, None)

    def open_le(self, sid, d):
        v, i = self._idx(sid, d)
        return (v[0][i], v[1][i]) if v else (None, None)

    def has(self, sid, d):
        return d in self.dset.get(sid, ())

    def open_on(self, sid, d):
        if not self.has(sid, d):
            return None
        v, i = self._idx(sid, d)
        return v[1][i]


@dataclass
class Fill:
    sid: int
    side: str
    qty: Decimal
    price: Decimal
    notional: Decimal  # signed, + buy
    cost: Decimal
    order_date: date
    fill_date: date
    bar_date: date  # session the price came from
    deferred_sessions: int


@dataclass
class Order:
    sid: int
    side: str
    cash: Decimal = ZERO  # buy amount
    qty: Decimal = ZERO  # sell shares
    order_date: date = None
    expire_idx: int = 10**9
    placed_idx: int = 0


@dataclass
class Out:
    policy: str
    fills: list = field(default_factory=list)
    orders: list = field(default_factory=list)  # (rebalance, sid, side, |planned notional|, bar_on_fill_date)
    expired: list = field(default_factory=list)  # (order, planned notional)
    rebal: list = field(default_factory=list)
    daily: list = field(default_factory=list)  # (date, nav, stale_mark_value)
    final_nav: Decimal = ZERO
    replay_nav: Decimal = ZERO


def run(policy, px, universe_rows, sessions, start, end, cap, fresh_signal=False):
    sidx = {d: i for i, d in enumerate(sessions)}
    firsts = {}
    for d in sessions:
        if start <= d <= end:
            firsts.setdefault((d.year, d.month), d)
    fills_dates = [firsts[k] for k in sorted(firsts)]
    o = Out(policy)
    cash, qty = cap, {}
    pending: list[Order] = []

    def mark(sid, d, decision):
        p = px.open_on(sid, d)
        if p is not None:
            return p, False
        return px.close_le(sid, decision)[1], True

    def execute(order, d, i):
        nonlocal cash
        p = px.open_on(order.sid, d)
        if p is None or p <= 0:
            return False
        if order.side == "SELL":
            q = min(order.qty, qty.get(order.sid, ZERO))
            notional = -(q * p)
        else:
            notional = order.cash
            q = notional / p
        c = abs(notional) * COST
        cash -= notional + c
        qty[order.sid] = qty.get(order.sid, ZERO) + (q if order.side == "BUY" else -q)
        if qty[order.sid] == 0:
            del qty[order.sid]
        o.fills.append(Fill(order.sid, order.side, q, p, notional, c, order.order_date, d, d,
                            i - order.placed_idx))
        return True

    def work_pending(d, i):
        nonlocal pending
        keep = []
        # sells first, then buys
        for od in sorted(pending, key=lambda x: (x.side != "SELL", x.sid)):
            if i > od.expire_idx:
                o.expired.append(od)
                continue
            if not execute(od, d, i):
                keep.append(od)
        pending = keep

    next_fill_i = 0
    for d in sessions:
        if d < fills_dates[0] or d > end:
            continue
        i = sidx[d]
        if next_fill_i < len(fills_dates) and d == fills_dates[next_fill_i]:
            F = d
            D = sessions[i - 1]
            next_fill_i += 1
            # expire non-persistent pending orders at a new rebalance
            if policy != "P0":
                still = []
                for od in pending:
                    if policy == "D" and od.side == "SELL":
                        continue  # re-issued below from fresh plan
                    o.expired.append(od)
                pending = still
            # --- signal ---
            sigs = []
            for sid, listed, gone in universe_rows:
                if listed > D or (gone is not None and D > gone):
                    continue
                if (D - listed).days < 252:
                    continue
                if fresh_signal and not px.has(sid, D):
                    continue
                pt = px.close_le(sid, D)[1]
                p3 = px.close_le(sid, months_before(D, 3))[1]
                p6 = px.close_le(sid, months_before(D, 6))[1]
                p12 = px.close_le(sid, months_before(D, 12))[1]
                if None in (pt, p3, p6, p12):
                    continue
                r3, r6, r12 = pt / p3 - 1, pt / p6 - 1, pt / p12 - 1
                sigs.append((W * r3 + W * r6 + W * r12, r12, r6, r3, sid))
            ranked = sorted(sigs, key=lambda s: (-s[0], -s[1], -s[2], -s[3]))
            rank = {s[4]: k for k, s in enumerate(ranked, 1)}
            held = frozenset(qty)
            kept = {s for s in held if rank.get(s, BUF + 1) <= BUF}
            adds = [s[4] for s in ranked[:N] if s[4] not in kept][: max(N - len(kept), 0)]
            target = frozenset(kept | set(adds))
            # --- marks & plan ---
            if policy == "P0":
                marks = {}
                for sid, q in qty.items():
                    _, p = px.open_le(sid, F)
                    marks[sid] = q * p if p is not None else ZERO
                nav_pre = cash + sum(marks.values())
                tv = nav_pre / len(target) if target else ZERO
                trades = []
                for sid in sorted(set(target) | set(qty)):
                    delta = (tv if sid in target else ZERO) - marks.get(sid, ZERO)
                    if delta != 0:
                        trades.append((sid, delta))
                total_cost = sum((abs(t) * COST for _, t in trades), ZERO)
                for sid, delta in trades:
                    bd, p = px.open_le(sid, F)
                    o.orders.append((F, sid, "BUY" if delta > 0 else "SELL", abs(delta), px.has(sid, F)))
                    if p is None or p <= 0:
                        continue
                    o.fills.append(Fill(sid, "BUY" if delta > 0 else "SELL", delta / p, p, delta,
                                        abs(delta) * COST, F, F, bd, 0))
                invested = ZERO
                newq = {}
                for sid in sorted(target):
                    _, p = px.open_le(sid, F)
                    if p is None or p <= 0:
                        continue
                    newq[sid] = tv / p
                    invested += tv
                qty = newq
                cash = nav_pre - invested - total_cost
                o.rebal.append(dict(F=str(F), D=str(D), nav_pre=nav_pre, target=sorted(target),
                                    eligible_scored=len(ranked)))
            else:
                marks, stale = {}, set()
                for sid, q in qty.items():
                    p, st = mark(sid, F, D)
                    marks[sid] = q * p
                    if st:
                        stale.add(sid)
                nav_pre = cash + sum(marks.values())
                tv = nav_pre / len(target) if target else ZERO
                sells, buys = [], []
                for sid in sorted(set(target) | set(qty)):
                    cur = marks.get(sid, ZERO)
                    want = tv if sid in target else ZERO
                    delta = want - cur
                    if delta == 0:
                        continue
                    o.orders.append((F, sid, "BUY" if delta > 0 else "SELL", abs(delta), px.has(sid, F)))
                    if delta < 0:
                        sq = qty[sid] if sid not in target else (-delta) / (marks[sid] / qty[sid])
                        sells.append(Order(sid, "SELL", qty=sq, order_date=F))
                    else:
                        buys.append(Order(sid, "BUY", cash=delta, order_date=F))
                window = {"A": 0, "C5": 4, "B": 10**9, "D": None}[policy]
                for od in sells + buys:
                    od.placed_idx = i
                    if policy == "D":
                        od.expire_idx = i if od.side == "BUY" else 10**9
                    else:
                        od.expire_idx = i + window
                # sells first
                for od in sells:
                    if not execute(od, F, i):
                        pending.append(od)
                # buy budget: no leverage
                need = sum((b.cash * (1 + COST) for b in buys), ZERO)
                held_back = sum((b.cash * (1 + COST) for b in pending if b.side == "BUY"), ZERO)
                budget = cash - held_back
                scale = min(Decimal(1), budget / need) if need > 0 else Decimal(1)
                if scale < 1:
                    for b in buys:
                        b.cash *= max(scale, ZERO)
                for od in buys:
                    if od.cash <= 0:
                        continue
                    if not execute(od, F, i):
                        pending.append(od)
                o.rebal.append(dict(F=str(F), D=str(D), nav_pre=nav_pre, target=sorted(target),
                                    eligible_scored=len(ranked), stale_marks=len(stale),
                                    scale=scale))
        elif policy != "P0":
            work_pending(d, i)
        # daily valuation at close
        nav, stale_val, vals = cash, ZERO, []
        for sid, q in qty.items():
            bd, c = px.close_le(sid, d)
            nav += q * c
            vals.append(q * c)
            if bd != d:
                stale_val += q * c
        o.daily.append((d, nav, stale_val, cash, len(vals), max(vals, default=ZERO)))
    # final NAV, same convention as the runner: adj_close on or before end
    o.final_nav = cash + sum((q * px.close_le(sid, end)[1] for sid, q in qty.items()), ZERO)
    # replay from fills (production's reconstruction rule)
    c2, q2 = cap, {}
    for f in sorted(o.fills, key=lambda f: (f.fill_date, f.sid)):
        c2 -= f.notional + f.cost
        q2[f.sid] = q2.get(f.sid, ZERO) + (f.qty if f.side == "BUY" or policy == "P0" else -f.qty)
    o.replay_nav = c2 + sum((q * px.close_le(s, end)[1] for s, q in q2.items() if q != 0), ZERO)
    return o
