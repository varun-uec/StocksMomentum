"""Independent weekly and monthly aggregation check against the API (read-only GETs).
Rebuilds 1W and 1M bars from the API's own daily bars: open of the first session,
max high, min low, close of the last session, summed volume."""
import json, sys, datetime as dt, urllib.request
BASE = "http://localhost:8000/api/v1"
def get(sym, interval):
    return json.load(urllib.request.urlopen(f"{BASE}/securities/{sym}/ohlcv?interval={interval}"))
def agg(bars, key):
    groups = {}
    for b in bars:
        groups.setdefault(key(dt.date.fromisoformat(b["date"])), []).append(b)
    out = []
    for k in sorted(groups):
        g = groups[k]
        out.append(dict(open=g[0]["open"], high=max(g, key=lambda x: float(x["high"]))["high"],
                        low=min(g, key=lambda x: float(x["low"]))["low"], close=g[-1]["close"],
                        volume=sum(x["volume"] for x in g), last=g[-1]["date"], n=len(g)))
    return out
tot = 0
for sym in sys.argv[1:]:
    d = get(sym, "1D"); w = get(sym, "1W"); m = get(sym, "1M")
    for name, api, key in (("1W", w, lambda x: x.isocalendar()[:2]), ("1M", m, lambda x: (x.year, x.month))):
        ref = agg(d["bars"], key)
        a = api["bars"]
        bad = 0
        if len(ref) != len(a):
            print(sym, name, "COUNT", len(ref), len(a)); bad += 1
        for r, x in zip(ref, a):
            if (r["open"], r["high"], r["low"], r["close"], r["volume"]) != (x["open"], x["high"], x["low"], x["close"], x["volume"]):
                bad += 1
                if bad <= 3: print(sym, name, "DIFF", r, x)
        print(f"{sym} {name}: api bars {len(a)}, reference bars {len(ref)}, mismatches {bad}, last api date {a[-1]['date']} partial={a[-1].get('partial')}")
        tot += bad
print("TOTAL MISMATCHES", tot)
