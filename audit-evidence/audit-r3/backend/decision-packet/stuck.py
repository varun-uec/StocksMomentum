from datetime import timedelta, date
import load, sim, compare
from momentum25.infrastructure.calendar.nse_calendar import get_nse_trading_calendar
S,E,C=compare.START,compare.END,compare.CAP
bars=load.load_bars(); px=sim.Px(bars,S-timedelta(days=400),E)
ses=get_nse_trading_calendar().sessions_between(sim.months_before(S,13),E)
secs={int(r['id']):r for r in load.securities()}
sidx={d:i for i,d in enumerate(ses)}
for ex in [("NSE",),("NSE","BOTH")]:
  for fresh in [False,True]:
    for p in ["A","D"]:
        o=sim.run(p,px,compare.universe_rows(ex),ses,S,E,C,fresh_signal=fresh)
        # rebuild end holdings from fills
        q={}
        for f in o.fills: q[f.sid]=q.get(f.sid,0)+(f.qty if f.side=="BUY" else -f.qty)
        held={s:v for s,v in q.items() if v>0}
        nav=o.final_nav
        rows=[]
        for s,v in held.items():
            bd,c=px.close_le(s,E); val=v*c
            gap=sidx[E]-sidx[bd]
            rows.append((gap,secs[s]['symbol'],str(bd),secs[s]['delisting_date'] or '-',float(val/nav)))
        stuck=[r for r in rows if r[0]>20]
        print("+".join(ex),"fresh" if fresh else "-",p,"end holdings",len(rows),"no bar >20 sessions:",len(stuck),"weight",round(sum(r[4] for r in stuck),4))
        for r in sorted(stuck)[-6:]: print("    ",r)
