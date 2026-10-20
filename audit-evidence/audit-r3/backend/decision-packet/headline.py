"""Headline table: return, CAGR, max drawdown, and a lower bound with non-trading positions at zero."""
import json
from datetime import timedelta
import load, sim, compare
from momentum25.infrastructure.calendar.nse_calendar import get_nse_trading_calendar
S, E, C = compare.START, compare.END, compare.CAP
bars = load.load_bars(); px = sim.Px(bars, S - timedelta(days=400), E)
ses = get_nse_trading_calendar().sessions_between(sim.months_before(S, 13), E)
sidx = {d: i for i, d in enumerate(ses)}
res = {}
for ex in [("NSE",), ("NSE", "BOTH")]:
    rows = compare.universe_rows(ex)
    for fresh in [False, True]:
        for p in ["P0", "A", "C5", "B", "D"]:
            o = sim.run(p, px, rows, ses, S, E, C, fresh_signal=fresh)
            m = compare.metrics(o, px, C)
            q = {}
            for f in o.fills:
                q[f.sid] = q.get(f.sid, 0) + (f.qty if (p == "P0" or f.side == "BUY") else -f.qty)
            dead = sum(v * px.close_le(s, E)[1] for s, v in q.items() if v > 0 and sidx[E] - sidx[px.close_le(s, E)[0]] > 20)
            lb = (o.final_nav - dead) / C - 1
            res[f"{'+'.join(ex)}{'-fresh' if fresh else ''}-{p}"] = dict(
                total_return=round(m["total_return"], 4), cagr=round(m["cagr"], 4), mdd=round(m["max_drawdown"], 4),
                zero_mark_lower_bound=round(float(lb), 4), stale_fill_pct=round(m["stale_filled_notional_pct"], 4),
                orders_no_bar_pct=round(m["orders_no_bar_pct"], 4), turnover=round(m["one_way_turnover_annual"], 3),
                costs=round(m["costs"]), mean_cash=round(m["mean_cash_weight_at_rebalance"], 4),
                max_cash=round(m["max_cash_weight_at_rebalance"], 4), holdings=round(m["mean_holdings"], 1),
                max_weight=round(m["max_single_weight"], 4), stale_mark=round(m["mean_stale_mark_weight"], 4),
                expired=m["expired_orders"], deferred=m["deferred_fills"], fills=m["fills"],
                filled_notional=round(m["filled_notional"]), jaccard=round(m.get("mean_target_jaccard_vs_P0", 1), 3))
for k, v in res.items():
    print(k, v)
json.dump(res, open("headline.json", "w"), indent=1)
