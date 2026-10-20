"""Run every policy, check P0 against the production run, and print the comparison."""
from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from decimal import Decimal

import load
import sim
from momentum25.infrastructure.calendar.nse_calendar import get_nse_trading_calendar

START, END, CAP = date(2025, 1, 1), date(2026, 7, 31), Decimal("1000000")


def universe_rows(exchanges):
    return [(sid, a, b) for sid, a, b in load.universe_provider(exchanges)._rows]


def metrics(o, px, cap):
    f = o.fills
    tot = sum(abs(x.notional) for x in f)
    stale = [x for x in f if not px.has(x.sid, x.fill_date) or x.bar_date != x.fill_date]
    st = sum(abs(x.notional) for x in stale)
    orders = len(o.orders)
    no_bar = [r for r in o.orders if not r[4]]
    planned = sum(r[3] for r in o.orders)
    no_bar_notional = sum(r[3] for r in no_bar)
    deferred = [x for x in f if x.deferred_sessions > 0]
    navs = [r[1] for r in o.daily]
    peak, mdd = navs[0], Decimal(0)
    for v in navs:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1)
    days = (END - date.fromisoformat(o.rebal[0]["F"])).days
    tr = o.final_nav / cap - 1
    cagr = float(o.final_nav / cap) ** (365.25 / days) - 1
    rb = [r for r in o.daily if str(r[0]) in {x["F"] for x in o.rebal}]
    cash_w = [float(r[3] / r[1]) for r in rb]
    max_w = [float(r[5] / r[1]) for r in rb]
    hold = [r[4] for r in rb]
    stale_mark_w = [float(r[2] / r[1]) for r in o.daily]
    mean_nav = sum(navs) / len(navs)
    years = Decimal(days) / Decimal("365.25")
    return dict(
        policy=o.policy,
        orders=orders,
        orders_no_bar_on_fill_date=len(no_bar),
        orders_no_bar_pct=len(no_bar) / orders,
        planned_notional=float(planned),
        no_bar_planned_notional_pct=float(no_bar_notional / planned),
        fills=len(f),
        filled_notional=float(tot),
        stale_fills=len(stale),
        stale_filled_notional_pct=float(st / tot) if tot else 0.0,
        deferred_fills=len(deferred),
        deferred_sessions_max=max((x.deferred_sessions for x in deferred), default=0),
        expired_orders=len(o.expired),
        costs=float(sum(x.cost for x in f)),
        one_way_turnover_annual=float(tot / 2 / mean_nav / years),
        final_nav=float(o.final_nav),
        replay_nav=float(o.replay_nav),
        total_return=float(tr),
        cagr=cagr,
        max_drawdown=float(mdd),
        mean_cash_weight_at_rebalance=sum(cash_w) / len(cash_w),
        max_cash_weight_at_rebalance=max(cash_w),
        mean_holdings=sum(hold) / len(hold),
        max_single_weight=max(max_w),
        mean_stale_mark_weight=sum(stale_mark_w) / len(stale_mark_w),
        max_stale_mark_weight=max(stale_mark_w),
        buy_scale_min=float(min((r.get("scale", 1) for r in o.rebal))),
    )


def main():
    exchanges = tuple(sys.argv[1].split(",")) if len(sys.argv) > 1 else ("NSE",)
    fresh = len(sys.argv) > 2 and sys.argv[2] == "fresh"
    tag = "+".join(exchanges) + ("-fresh" if fresh else "")
    bars = load.load_bars()
    px = sim.Px(bars, START - timedelta(days=400), END)
    sessions = get_nse_trading_calendar().sessions_between(sim.months_before(START, 13), END)
    rows = universe_rows(exchanges)
    results, runs = [], {}
    for p in ["P0", "A", "C5", "B", "D"]:
        o = sim.run(p, px, rows, sessions, START, END, CAP, fresh_signal=fresh)
        runs[p] = o
        results.append(metrics(o, px, CAP))
    # holdings overlap with P0 per rebalance
    for r in results:
        o = runs[r["policy"]]
        ov = [len(set(a["target"]) & set(b["target"])) / max(len(set(a["target"]) | set(b["target"])), 1)
              for a, b in zip(o.rebal, runs["P0"].rebal)]
        r["mean_target_jaccard_vs_P0"] = sum(ov) / len(ov)
    json.dump(results, open(f"compare-{tag}.json", "w"), indent=1, default=str)
    keys = list(results[0].keys())
    print("universe", tag)
    for k in keys:
        print(f"{k:34s}" + "".join(f"{str(round(r[k], 4) if isinstance(r[k], float) else r[k]):>16s}" for r in results))
    if exchanges == ("NSE",) and not fresh:
        audit = json.load(open("wf_repro.json"))
        p0 = runs["P0"]
        print("P0 final_nav == production:", Decimal(audit["final_nav"]) == p0.final_nav, p0.final_nav, audit["final_nav"])
        prod_sel = [sorted(r["selected"]) for r in audit["rebalances"]]
        print("P0 targets == production:", prod_sel == [r["target"] for r in p0.rebal])
        print("P0 trade count == production:", len(p0.fills) == audit["trade_count"])
        # dump stale-fill detail for the root-cause table
        with open("p0_stale_detail.csv", "w") as fh:
            fh.write("security_id,side,fill_date,bar_date,price,notional,sessions_stale,has_bar_on_decision\n")
            sidx = {d: i for i, d in enumerate(sessions)}
            for x in p0.fills:
                if x.bar_date != x.fill_date:
                    D = sessions[sidx[x.fill_date] - 1]
                    gap = sidx[x.fill_date] - sidx[x.bar_date] if x.bar_date in sidx else -1
                    fh.write(f"{x.sid},{x.side},{x.fill_date},{x.bar_date},{x.price},{x.notional},{gap},{px.has(x.sid, D)}\n")


if __name__ == "__main__":
    main()
