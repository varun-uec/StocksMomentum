"""RS window alignment and forward-return measurement, In-Sample only.

CA: population C; R(d) anchored on the exchange session d sessions before the run
    date; the anchor bar must lie within 5 sessions of that session, else R(d) is
    undefined and the name gets no rating.
Forward returns two ways:
    stored  : forward_returns table (the security's own next h bars)
    session : last bar on or before exchange session t+h (exit <= 2022-12-30)
"""
import json
from bisect import bisect_right
from statistics import mean

import rs_ref as R

TOL = 5


def rs_aligned(pop, as_of):
    i0 = R.SIDX[max(d for d in R.SESS if d <= as_of)]
    rets = []
    for sid in pop:
        rows = R.full.get(sid, [])
        ds = R.DATES.get(sid, [])
        k = bisect_right(ds, as_of) - 1
        if k < 0:
            continue
        px = lambda j: float(rows[j][7] if rows[j][7] is not None else rows[j][4])
        latest = px(k)
        ws = tw = 0.0
        ok = True
        for p, w in R.RSW.items():
            target = R.SESS[i0 - p]
            j = bisect_right(ds, target) - 1
            if j < 0 or R.SIDX.get(ds[j], -10**6) < i0 - p - TOL:
                ok = False
                break
            ws += w * (latest / px(j) - 1); tw += w
        if ok and tw > 0:
            rets.append((ws / tw, sid))
    rets.sort(key=lambda x: x[0])
    n = len(rets)
    return {sid: max(1, min(99, int(round(i / (n - 1) * 98)) + 1)) for i, (_, sid) in enumerate(rets)}


def fwd_session(sid, as_of, h):
    i0 = R.SIDX[as_of]
    exit_d = R.SESS[i0 + h]
    if exit_d > R.IS_EXIT_LIMIT:
        return None
    ds, rows = R.DATES.get(sid, []), R.full.get(sid, [])
    a, b = bisect_right(ds, as_of) - 1, bisect_right(ds, exit_d) - 1
    if a < 0 or b <= a:
        return None
    pa = float(rows[a][4] * rows[a][6]); pb = float(rows[b][4] * rows[b][6])
    return pb / pa - 1 if pa > 0 else None


res = []
for run, as_of in sorted(R.runs.items(), key=lambda x: x[1]):
    pops, comp = R.populations(as_of)
    row = dict(date=str(as_of))
    tops = {}
    for k, ratings in (("A", R.rs(pops["A"], as_of)), ("C", R.rs(pops["C"], as_of)), ("CA", rs_aligned(pops["C"], as_of))):
        rk = R.ranked(run, ratings)
        top = [s for s, _ in rk[:25]]
        tops[k] = top
        row[f"{k}_qualified"] = len(rk)
        row[f"{k}_rated"] = len(ratings)
        for h in (60, 120):
            st = [R.fr[(run, h)][s] for s in top if s in R.fr[(run, h)]]
            se = [x for x in (fwd_session(s, as_of, h) for s in top) if x is not None]
            row[f"{k}_fwd{h}_stored"] = mean(st) if st else None
            row[f"{k}_fwd{h}_session"] = mean(se) if se else None
        row[f"{k}_gap_names_top25"] = sum(1 for s in top if comp.get(s, 0) < .95)
    row["CA_overlap_A"] = len(set(tops["CA"]) & set(tops["A"]))
    row["C_overlap_A"] = len(set(tops["C"]) & set(tops["A"]))
    # gap vs no-gap names in A's Top-25, both forward-return definitions
    gap = [s for s in tops["A"] if comp.get(s, 0) < .95]
    nog = [s for s in tops["A"] if s not in gap]
    for lab, grp in (("gap", gap), ("nogap", nog)):
        st = [R.fr[(run, 120)][s] for s in grp if s in R.fr[(run, 120)]]
        se = [x for x in (fwd_session(s, as_of, 120) for s in grp) if x is not None]
        row[f"A_{lab}_fwd120_stored"] = mean(st) if st else None
        row[f"A_{lab}_fwd120_session"] = mean(se) if se else None
    res.append(row)


def avg(key):
    v = [r[key] for r in res if r.get(key) is not None]
    return (round(mean(v), 4), len(v)) if v else (None, 0)


summary = {k: avg(k) for k in res[0] if k != "date"}
print(json.dumps(summary, indent=1))
json.dump(dict(rows=res, summary=summary), open("rs_align.json", "w"), indent=1)
