import sys
from datetime import timedelta
import load, sim, compare
from momentum25.infrastructure.calendar.nse_calendar import get_nse_trading_calendar
S,E,C=compare.START,compare.END,compare.CAP
bars=load.load_bars(); px=sim.Px(bars,S-timedelta(days=400),E)
ses=get_nse_trading_calendar().sessions_between(sim.months_before(S,13),E)
sym={r['symbol']:int(r['id']) for r in load.securities()}
p0=sim.run("P0",px,compare.universe_rows(("NSE",)),ses,S,E,C)
for name in sys.argv[1:]:
    sid=sym[name]; print("==",name,sid)
    for f in p0.fills:
        if f.sid==sid: print(f"  {f.fill_date} {f.side:4s} px {float(f.price):9.2f} from bar {f.bar_date} notional {float(f.notional):10.0f}")
    ds,os_,cs,vs=px.s[sid]
    gaps=[(ds[i-1],ds[i],(ds[i]-ds[i-1]).days) for i in range(1,len(ds)) if (ds[i]-ds[i-1]).days>10]
    print("  bar gaps >10d:",[(str(a),str(b),g) for a,b,g in gaps][:8])
    for a,b,g in gaps[:4]:
        i=ds.index(b); print(f"   resume {b}: close before {float(cs[i-1]):.2f} -> open {float(os_[i]):.2f} close {float(cs[i]):.2f} vol {vs[i]}")
    print("  last bar", ds[-1], float(cs[-1]), "bars in window", len(ds))
