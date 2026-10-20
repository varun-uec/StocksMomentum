"""R3-B-10 item 1 over seven more runs: RS over all equities (code) vs over eligible names (spec).

Both variants are recomputed on today's data, so the comparison is like for like.
Other rules keep their stored contributions. Stored RS also checked (pre-18cab43
runs used raw closes, so mismatches there are expected and reported).
"""
import csv
import json
from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal

import load
from momentum25.domain.value_objects.instrument import is_equity

RUNS = {14: "2020-11-27", 88: "2021-08-31", 98: "2022-06-30", 43: "2023-04-28",
        117: "2024-01-31", 62: "2024-11-29", 72: "2025-09-30"}
MW = {"relative_strength": 2, "volume_accumulation": 1, "pattern": 1, "breakout": 1.5,
      "momentum_quality": 1, "risk": 0.5}
SW = {"breakout": 3, "volume_accumulation": 2, "pattern": 1.5, "risk": 1.5, "relative_strength": 1}
RSW = {63: 0.4, 126: 0.2, 189: 0.2, 252: 0.2}
secs = {int(r["id"]): r for r in load.securities()}
sym = {s: r["symbol"] for s, r in secs.items()}


def q4(x):
    return Decimal(x).quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)


def rs(universe, bars):
    rets = []
    for sid in universe:
        b = bars.get(sid, [])[-257:]
        if len(b) < 2:
            continue
        adj = [float(a if a is not None else c) for c, a in b]
        ws = tw = 0.0
        for p, w in RSW.items():
            win = min(p, len(b) - 1)
            if win <= 0 or adj[-(win + 1)] <= 0:
                continue
            ws += w * (adj[-1] / adj[-(win + 1)] - 1)
            tw += w
        if tw > 0:
            rets.append((ws / tw, sid))
    rets.sort(key=lambda x: x[0])
    n = len(rets)
    return {sid: max(1, min(99, int(round(i / (n - 1) * 98)) + 1)) for i, (_, sid) in enumerate(rets)}


out = []
for run, d in RUNS.items():
    as_of = date.fromisoformat(d)
    p = f"data/runs/"
    rr = defaultdict(dict)
    for r in csv.DictReader(open(p + f"rr{run}.csv")):
        rr[int(r["security_id"])][r["rule_id"]] = r
    um = {int(r["security_id"]): r["eligible"] == "t" for r in csv.DictReader(open(p + f"um{run}.csv"))}
    sr = {int(r["security_id"]): r for r in csv.DictReader(open(p + f"sr{run}.csv"))}
    bars = defaultdict(list)
    for r in csv.DictReader(open(p + f"bars{run}.csv")):
        bars[int(r["security_id"])].append((Decimal(r["close"]), Decimal(r["adj_close"]) if r["adj_close"] else None))
    uni = [s for s, r in secs.items() if r["is_active"] == "t" and is_equity(r["isin"] or None)
           and (not r["listing_date"] or date.fromisoformat(r["listing_date"]) <= as_of)]
    cur = rs(uni, bars)
    eq = lambda s: s in secs and is_equity(secs[s]["isin"] or None)
    alt = rs([s for s, e in um.items() if e and eq(s)], bars)
    scored = sorted(s for s in rr if "tt_rs_rating_min" in rr[s] and eq(s))
    stored_match = sum(1 for s in scored if Decimal(rr[s]["tt_rs_rating_min"]["raw_value"]) == cur.get(s))
    gates = [k for k in rr[scored[0]] if k.startswith("tt_")]

    def rank(rmap):
        rows = []
        for s in scored:
            v = rmap.get(s)
            if v is None or not all(rr[s][g]["passed"] == "t" for g in gates if g != "tt_rs_rating_min") or v < 70:
                continue
            ov = {"rs_rating": Decimal(2) * min(max((Decimal(v) - 70) / 29, Decimal(0)), Decimal(1))}
            eng = defaultdict(lambda: [Decimal(0), Decimal(0)])
            for rid, r in sorted(rr[s].items()):
                eng[r["engine_id"]][0] += ov.get(rid, Decimal(r["contribution"]))
                eng[r["engine_id"]][1] += Decimal(r["weight"])
            es = {e: (a / b if b else Decimal(0)) for e, (a, b) in eng.items()}
            m = 100 * sum(Decimal(str(w)) * es.get(e, 0) for e, w in MW.items()) / sum(Decimal(str(w)) for w in MW.values())
            b_ = 100 * sum(Decimal(str(w)) * es.get(e, 0) for e, w in SW.items()) / sum(Decimal(str(w)) for w in SW.values())
            rows.append((-q4(m), -q4(b_), -v, s))
        rows.sort()
        return [r[-1] for r in rows]

    rc, ra = rank(cur), rank(alt)
    both = [s for s in scored if s in cur and s in alt]
    out.append(dict(
        run=run, date=d, rs_universe_code=len(cur), rs_universe_spec=len(alt), scored=len(scored),
        stored_rs_reproduced=f"{stored_match}/{len(scored)}",
        ratings_changed=sum(1 for s in both if cur[s] != alt[s]),
        cross_70_up=sum(1 for s in both if cur[s] < 70 <= alt[s]),
        cross_70_down=sum(1 for s in both if alt[s] < 70 <= cur[s]),
        qualified_code=len(rc), qualified_spec=len(ra),
        top25_overlap=len(set(rc[:25]) & set(ra[:25])),
        top25_entered=[sym[s] for s in ra[:25] if s not in rc[:25]],
        top25_left=[sym[s] for s in rc[:25] if s not in ra[:25]],
    ))
    print(json.dumps(out[-1]))
json.dump(out, open("r3b10_multi.json", "w"), indent=1)
