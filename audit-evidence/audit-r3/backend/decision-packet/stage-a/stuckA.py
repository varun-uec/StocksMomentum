"""Who are the non-trading holdings at the end under the corrected configuration?"""
import json, collections
from datetime import date, timedelta
from decimal import Decimal
import load, sim, sim2, stageA
S, E = date(2021, 1, 1), date(2026, 7, 31)
full = load.load_bars("ohlcv_full")
ses = stageA.CAL.sessions_between(sim.months_before(S, 13), E)
sidx = {d: i for i, d in enumerate(ses)}
px = sim2.Px(full, S - timedelta(days=400), E, "computed"); stageA.PX = px
o = sim2.run(px, stageA.universe(("NSE", "BOTH"), True), ses, S, E, stageA.CAP, buy_window=4)
secs = stageA.SECS
last_any = {sid: rows[-1][0] for sid, rows in full.items()}
rows = []
for s, q in o.qty.items():
    bd, c = px.close_le(s, E)
    gap = sidx[E] - sidx[bd]
    if gap > 20:
        rows.append(dict(symbol=secs[s]["symbol"], last_bar_in_window=str(bd), sessions_since=gap,
                         trades_again_later=last_any[s] > E, delisting_date=secs[s]["delisting_date"] or None,
                         weight=round(float(q * c / o.final_nav), 4)))
rows.sort(key=lambda r: -r["weight"])
print("end holdings", len(o.qty), "non-trading >20 sessions", len(rows), "weight", round(sum(r["weight"] for r in rows), 4))
print("resume trading after window end:", sum(r["trades_again_later"] for r in rows), "never again (as of 2026-10-19):", sum(not r["trades_again_later"] for r in rows))
print("sessions since last bar: median", sorted(r["sessions_since"] for r in rows)[len(rows)//2], "max", max(r["sessions_since"] for r in rows))
for r in rows[:15]: print(r)
json.dump(rows, open("stuckA.json", "w"), indent=1)
