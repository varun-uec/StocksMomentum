"""Stage A backtest grid: corrected universe and price source, execution-policy sensitivity.

1. Cross-check: sim2 with the production price source and NSE-only universe must
   reproduce sim.py policy D (current signal and E1) final NAV exactly.
2. Grid on the corrected configuration over two windows.
"""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from decimal import Decimal

import load
import sim
import sim2
from momentum25.domain.value_objects.instrument import is_equity
from momentum25.infrastructure.calendar.nse_calendar import get_nse_trading_calendar

CAP = Decimal("1000000")
CAL = get_nse_trading_calendar()
SECS = {int(r["id"]): r for r in load.securities()}


def universe(exchanges, equity_only):
    rows = []
    for r in load.securities():
        if r["exchange"] not in exchanges or not r["listing_date"]:
            continue
        if equity_only and not is_equity(r["isin"] or None):
            continue
        rows.append((int(r["id"]), load.d(r["listing_date"]), load.d(r["delisting_date"])))
    return rows


def metrics(o, start, end, sessions):
    sidx = {d: i for i, d in enumerate(sessions)}
    f = o.fills
    tot = sum((abs(x.notional) for x in f), Decimal(0))
    navs = [r[1] for r in o.daily]
    peak, mdd = navs[0], Decimal(0)
    for v in navs:
        peak = max(peak, v); mdd = min(mdd, v / peak - 1)
    days = (end - o.rebal[0]["F"]).days
    years = days / 365.25
    rb = {x["F"] for x in o.rebal}
    rows = [r for r in o.daily if r[0] in rb]
    dead = Decimal(0)
    for s, q in o.qty.items():
        bd, c = sim2.Px.close_le(PX, s, end)
        if sidx[end] - sidx[bd] > 20:
            dead += q * c
    parts = sorted(float(x.participation) for x in f if x.participation is not None)
    cancelled_buys = [c for c in o.cancelled if c[0].side == "BUY"]
    return dict(
        orders=len(o.orders), orders_no_bar_F=sum(1 for r in o.orders if not r[4]),
        fills=len(f), partial_fills=sum(1 for x in f if x.partial),
        deferred_fills=sum(1 for x in f if x.delay > 0), max_delay=max((x.delay for x in f), default=0),
        deferred_buy_fills=sum(1 for x in f if x.delay > 0 and x.side == "BUY"),
        cancelled_buys=len(cancelled_buys), cancelled_buy_notional=round(float(sum((c[1] for c in cancelled_buys), Decimal(0)))),
        superseded_sells=sum(1 for c in o.cancelled if c[0].side == "SELL"),
        end_pending=len(o.end_pending), filled_notional=round(float(tot)), costs=round(float(sum((x.cost for x in f), Decimal(0)))),
        turnover=round(float(tot / 2 / (sum(navs) / len(navs))) / years, 3),
        total_return=round(float(o.final_nav / CAP - 1), 4), cagr=round(float(o.final_nav / CAP) ** (1 / years) - 1, 4),
        mdd=round(float(mdd), 4), lower_bound=round(float((o.final_nav - dead) / CAP - 1), 4),
        nontrading_weight_end=round(float(dead / o.final_nav), 4),
        mean_cash=round(sum(float(r[3] / r[1]) for r in rows) / len(rows), 4), max_cash=round(max(float(r[3] / r[1]) for r in rows), 4),
        min_cash=round(float(o.min_cash), 2), mean_holdings=round(sum(r[4] for r in rows) / len(rows), 1),
        max_weight=round(max(float(r[5] / r[1]) for r in rows), 4),
        mean_nontrading_weight=round(sum(float(r[2] / r[1]) for r in o.daily) / len(o.daily), 4),
        participation_p99=round(parts[int(.99 * len(parts))], 4) if parts else None, participation_max=round(parts[-1], 4) if parts else None,
        fills_over_10pct=sum(1 for x in parts if x > .10),
        scored_min=min(r["scored"] for r in o.rebal), scored_max=max(r["scored"] for r in o.rebal),
        min_buy_scale=round(float(min(r["scale"] for r in o.rebal)), 4),
    )


def main():
    global PX
    out = {}
    # ---- 1. cross-check against sim.py policy D, production price source, NSE-only
    S, E = date(2025, 1, 1), date(2026, 7, 31)
    bars = load.load_bars()
    sessions = CAL.sessions_between(sim.months_before(S, 13), E)
    PX = sim2.Px(bars, S - timedelta(days=400), E, "adj_close")
    pxo = sim.Px(bars, S - timedelta(days=400), E)
    rows = universe(("NSE",), False)
    for fresh in (False, True):
        a = sim.run("D", pxo, rows, sessions, S, E, CAP, fresh_signal=fresh)
        b = sim2.run(PX, rows, sessions, S, E, CAP, require_decision_bar=fresh, buy_window=0, sell_retry=True)
        print("cross-check D fresh=%s" % fresh, a.final_nav == b.final_nav, a.final_nav, b.final_nav, len(a.fills), len(b.fills))
    # ---- 2. grid
    full = load.load_bars("ohlcv_full")
    configs = {
        "U0 current universe+price, E1, D": dict(uni=(("NSE",), False), src="adj_close", kw=dict(buy_window=0)),
        "U1 corrected universe, adj_close price, E1, D": dict(uni=(("NSE", "BOTH"), True), src="adj_close", kw=dict(buy_window=0)),
        "U2 corrected universe+price, E1, D (buy F only)": dict(uni=(("NSE", "BOTH"), True), src="computed", kw=dict(buy_window=0)),
        "U2 B1 (buy F..F+1)": dict(uni=(("NSE", "BOTH"), True), src="computed", kw=dict(buy_window=1)),
        "U2 B5 (buy F..F+4)": dict(uni=(("NSE", "BOTH"), True), src="computed", kw=dict(buy_window=4)),
        "U2 B (buy until next decision)": dict(uni=(("NSE", "BOTH"), True), src="computed", kw=dict(buy_window=None)),
        "U2 A (no sell retry)": dict(uni=(("NSE", "BOTH"), True), src="computed", kw=dict(buy_window=0, sell_retry=False)),
        "U2 B5 + cap 10%": dict(uni=(("NSE", "BOTH"), True), src="computed", kw=dict(buy_window=4, cap=Decimal("0.10"))),
        "U2 B5 + cap 2%": dict(uni=(("NSE", "BOTH"), True), src="computed", kw=dict(buy_window=4, cap=Decimal("0.02"))),
        "U2 B5 + T+1 settlement": dict(uni=(("NSE", "BOTH"), True), src="computed", kw=dict(buy_window=4, t1_settlement=True)),
        "U2 B5, no E1": dict(uni=(("NSE", "BOTH"), True), src="computed", kw=dict(buy_window=4, require_decision_bar=False)),
    }
    for (S, E) in [(date(2025, 1, 1), date(2026, 7, 31)), (date(2021, 1, 1), date(2026, 7, 31))]:
        sessions = CAL.sessions_between(sim.months_before(S, 13), E)
        cache = {}
        for name, c in configs.items():
            key = c["src"]
            if key not in cache:
                cache[key] = sim2.Px(full, S - timedelta(days=400), E, key)
            PX = cache[key]
            o = sim2.run(PX, universe(*c["uni"]), sessions, S, E, CAP, **{"require_decision_bar": True, "sell_retry": True, **c["kw"]})
            m = metrics(o, S, E, sessions)
            out[f"{S}..{E} | {name}"] = m
            print(f"{S}..{E} | {name}: " + json.dumps(m))
    json.dump(out, open("stageA_grid.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
