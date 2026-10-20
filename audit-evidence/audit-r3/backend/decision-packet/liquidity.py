"""Fill participation (|notional| / that session's traded value) and lookback-price staleness."""
import json
from datetime import timedelta
from decimal import Decimal
import load, sim, compare
from momentum25.infrastructure.calendar.nse_calendar import get_nse_trading_calendar
S, E, C = compare.START, compare.END, compare.CAP
bars = load.load_bars(); px = sim.Px(bars, S - timedelta(days=400), E)
ses = get_nse_trading_calendar().sessions_between(sim.months_before(S, 13), E)
sidx = {d: i for i, d in enumerate(ses)}
tv = {(sid, r[0]): r[8] for sid, rows in bars.items() for r in rows}
out = {}
for ex in [("NSE",), ("NSE", "BOTH")]:
    rows = compare.universe_rows(ex)
    for p, fresh in [("P0", False), ("A", False), ("D", False), ("A", True), ("D", True)]:
        o = sim.run(p, px, rows, ses, S, E, C, fresh_signal=fresh)
        parts = []
        for f in o.fills:
            t = tv.get((f.sid, f.bar_date))
            if t and t > 0:
                parts.append(float(abs(f.notional) / t))
        parts.sort()
        q = lambda x: parts[min(int(x * len(parts)), len(parts) - 1)]
        out[f"{'+'.join(ex)}-{p}{'-fresh' if fresh else ''}"] = dict(
            fills=len(o.fills), median=q(.5), p90=q(.9), p99=q(.99), max=parts[-1],
            over_10pct=sum(1 for x in parts if x > .10), over_100pct=sum(1 for x in parts if x > 1))
    # lookback staleness on scored names (fresh signal)
    gaps = []
    firsts = {}
    for d in ses:
        if S <= d <= E: firsts.setdefault((d.year, d.month), d)
    for F in firsts.values():
        D = ses[sidx[F] - 1]
        for sid, listed, gone in rows:
            if listed > D or (gone and D > gone) or (D - listed).days < 252 or not px.has(sid, D):
                continue
            for m in (3, 6, 12):
                tgt = sim.months_before(D, m)
                bd, _ = px.close_le(sid, tgt)
                if bd is None: break
                anchor = max(x for x in ses if x <= tgt)
                gaps.append(sidx[anchor] - sidx[bd] if bd in sidx else 999)
    out[f"{'+'.join(ex)}-lookback"] = dict(lookups=len(gaps), gt_5_sessions=sum(1 for g in gaps if g > 5),
                                          gt_20_sessions=sum(1 for g in gaps if g > 20))
print(json.dumps(out, indent=1))
json.dump(out, open("liquidity.json", "w"), indent=1)
