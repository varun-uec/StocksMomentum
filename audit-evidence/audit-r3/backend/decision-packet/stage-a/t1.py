import json
from datetime import date, timedelta
from decimal import Decimal
import load, sim, sim2, stageA
full = load.load_bars("ohlcv_full")
res = {}
for S, E in [(date(2025, 1, 1), date(2026, 7, 31)), (date(2021, 1, 1), date(2026, 7, 31))]:
    ses = stageA.CAL.sessions_between(sim.months_before(S, 13), E)
    px = sim2.Px(full, S - timedelta(days=400), E, "computed"); stageA.PX = px
    for name, kw in [("B5", dict(buy_window=4)), ("B5 + T+1", dict(buy_window=4, t1_settlement=True))]:
        o = sim2.run(px, stageA.universe(("NSE", "BOTH"), True), ses, S, E, stageA.CAP, **kw)
        m = stageA.metrics(o, S, E, ses)
        res[f"{S}..{E} | {name}"] = m
        print(S, E, name, {k: m[k] for k in ["fills", "deferred_buy_fills", "cancelled_buys", "total_return", "cagr", "mdd", "lower_bound", "min_cash", "turnover"]})
json.dump(res, open("t1.json", "w"), indent=1)
