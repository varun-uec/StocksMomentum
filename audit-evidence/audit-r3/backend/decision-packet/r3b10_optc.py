"""Item 1, option C: all equities, but only those with valid RS inputs
(>= 253 bars, last bar within 30 calendar days). Compared with code (A) and spec (B)."""
import csv, json, importlib.util
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
import load
from momentum25.domain.value_objects.instrument import is_equity
spec = importlib.util.spec_from_file_location("m", "r3b10_multi.py")
src = open("r3b10_multi.py").read().split("out = []")[0]
m = {}; exec(src, m)
RUNS = dict(m["RUNS"]); RUNS[149] = "2026-10-19"
secs = m["secs"]; sym = m["sym"]
res = []
for run, d in RUNS.items():
    as_of = date.fromisoformat(d)
    p = "data/runs/" if run != 149 else "data/"
    f = (lambda k: p + f"{k}{run}.csv") if run != 149 else (lambda k: {"rr": "data/rr149.csv", "um": "data/um149.csv", "sr": "data/sr149.csv", "bars": "data/rs_bars.csv"}[k])
    rr = defaultdict(dict)
    for r in csv.DictReader(open(f("rr"))): rr[int(r["security_id"])][r["rule_id"]] = r
    um = {int(r["security_id"]): r["eligible"] == "t" for r in csv.DictReader(open(f("um")))}
    bars, last = defaultdict(list), {}
    for r in csv.DictReader(open(f("bars"))):
        s = int(r["security_id"]); bars[s].append((Decimal(r["close"]), Decimal(r["adj_close"]) if r["adj_close"] else None)); last[s] = date.fromisoformat(r["date"])
    eq = lambda s: s in secs and is_equity(secs[s]["isin"] or None)
    uni = [s for s, r in secs.items() if r["is_active"] == "t" and eq(s) and (not r["listing_date"] or date.fromisoformat(r["listing_date"]) <= as_of)]
    A = m["rs"](uni, bars)
    B = m["rs"]([s for s, e in um.items() if e and eq(s)], bars)
    uc = [s for s in uni if len(bars.get(s, [])) >= 253 and last.get(s, date.min) >= as_of - timedelta(days=30)]
    C = m["rs"](uc, bars)
    scored = [s for s in rr if "tt_rs_rating_min" in rr[s] and eq(s)]
    gates = [k for k in rr[scored[0]] if k.startswith("tt_")]
    def qual(R):
        return {s for s in scored if R.get(s) is not None and R[s] >= 70 and all(rr[s][g]["passed"] == "t" for g in gates if g != "tt_rs_rating_min")}
    qa, qb, qc = qual(A), qual(B), qual(C)
    row = dict(run=run, date=d, n_A=len(A), n_B=len(B), n_C=len(uc),
               excluded_short=sum(1 for s in uni if len(bars.get(s, [])) < 253),
               excluded_stale=sum(1 for s in uni if len(bars.get(s, [])) >= 253 and last.get(s, date.min) < as_of - timedelta(days=30)),
               changed_C_vs_A=sum(1 for s in scored if s in A and s in C and A[s] != C[s]),
               changed_B_vs_C=sum(1 for s in scored if s in B and s in C and B[s] != C[s]),
               mean_abs_B_minus_C=sum(abs(B[s] - C[s]) for s in scored if s in B and s in C) / len(scored),
               qualified_A=len(qa), qualified_B=len(qb), qualified_C=len(qc),
               jaccard_qual_B_C=len(qb & qc) / len(qb | qc), jaccard_qual_A_B=len(qa & qb) / len(qa | qb))
    res.append(row); print(json.dumps(row))
json.dump(res, open("r3b10_optc.json", "w"), indent=1)
