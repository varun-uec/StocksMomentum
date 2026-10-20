"""Per-security P&L attribution, P0 vs A, from fills and end marks."""
import csv
from datetime import date, timedelta
from decimal import Decimal
import load, sim, compare
from momentum25.infrastructure.calendar.nse_calendar import get_nse_trading_calendar
S,E,C=compare.START,compare.END,compare.CAP
bars=load.load_bars(); px=sim.Px(bars,S-timedelta(days=400),E)
ses=get_nse_trading_calendar().sessions_between(sim.months_before(S,13),E)
rows=compare.universe_rows(("NSE",))
sym={int(r['id']):r['symbol'] for r in load.securities()}
def pnl(o):
    cash={};q={}
    for f in o.fills:
        sq=f.qty if (o.policy=="P0" or f.side=="BUY") else -f.qty
        cash[f.sid]=cash.get(f.sid,0)-f.notional-f.cost; q[f.sid]=q.get(f.sid,0)+sq
    return {s:cash[s]+q[s]*(px.close_le(s,E)[1] or 0) for s in cash}
p0=sim.run("P0",px,rows,ses,S,E,C); a=sim.run("A",px,rows,ses,S,E,C)
P,A=pnl(p0),pnl(a)
print("sum pnl P0",sum(P.values()),"A",sum(A.values()))
diff=sorted(set(P)|set(A),key=lambda s:(P.get(s,0)-A.get(s,0)))
print("Largest P0-minus-A P&L gaps:")
stale_sids={f.sid for f in p0.fills if f.bar_date!=f.fill_date}
for s in diff[:12]+diff[-5:]:
    print(f"{sym[s]:14s} P0 {float(P.get(s,0)):>12.0f}  A {float(A.get(s,0)):>12.0f}  gap {float(P.get(s,0)-A.get(s,0)):>12.0f} stale_in_P0={s in stale_sids}")
tot_gap=sum(P.values())-sum(A.values())
st_gap=sum(P.get(s,0)-A.get(s,0) for s in stale_sids)
print("total gap",float(tot_gap),"gap on names with a P0 stale fill",float(st_gap))
# P0: P&L of stale-filled names
print("P0 P&L on names with >=1 stale fill:",float(sum(P[s] for s in stale_sids)),"n",len(stale_sids))
print("P0 P&L on other names:",float(sum(v for s,v in P.items() if s not in stale_sids)))
