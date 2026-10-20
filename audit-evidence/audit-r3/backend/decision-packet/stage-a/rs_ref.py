"""RS reference universe: completeness, alignment, point-in-time status, and the
In-Sample screener impact of each candidate definition.

Variants (all equities, ISIN not a fund unit):
  A    code today: active, >= 2 bars, windows shortened to the bars available
  C    valid inputs: >= 253 bars, last bar not stale (> 30 days)
  CP   C, point-in-time: listing_date <= as_of instead of the current is_active flag
  C95  C plus window completeness: own bars cover >= 95% of the last 253 exchange sessions
In-Sample only: runs dated 2020-11-27 .. 2022-06-30, forward exits <= 2022-12-30.
The hold-out (2023-01-02 .. 2025-12-31) is not read.
"""
import csv
import json
from collections import defaultdict
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from statistics import mean

import load
from momentum25.domain.value_objects.instrument import is_equity
from momentum25.infrastructure.calendar.nse_calendar import get_nse_trading_calendar

RSW = {63: 0.4, 126: 0.2, 189: 0.2, 252: 0.2}
MW = {"relative_strength": 2, "volume_accumulation": 1, "pattern": 1, "breakout": 1.5, "momentum_quality": 1, "risk": 0.5}
SW = {"breakout": 3, "volume_accumulation": 2, "pattern": 1.5, "risk": 1.5, "relative_strength": 1}
IS_EXIT_LIMIT = date(2022, 12, 30)
CAL = get_nse_trading_calendar()
SESS = CAL.sessions_between(date(2018, 1, 1), date(2026, 10, 19))
SIDX = {d: i for i, d in enumerate(SESS)}
secs = {int(r["id"]): r for r in load.securities()}
sym = {s: r["symbol"] for s, r in secs.items()}
full = load.load_bars("ohlcv_full")
DATES = {sid: [r[0] for r in rows] for sid, rows in full.items()}


def q4(x):
    return Decimal(x).quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)


def series(sid, as_of, n=257):
    rows = full.get(sid, [])
    # bars on or before as_of
    from bisect import bisect_right
    k = bisect_right(DATES.get(sid, []), as_of)
    return rows[max(0, k - n):k]


def rs(pop, as_of):
    rets = []
    for sid in pop:
        b = series(sid, as_of)
        if len(b) < 2:
            continue
        adj = [float(x[7] if x[7] is not None else x[4]) for x in b]  # production: adj_close else close
        ws = tw = 0.0
        for p, w in RSW.items():
            win = min(p, len(b) - 1)
            if win <= 0 or adj[-(win + 1)] <= 0:
                continue
            ws += w * (adj[-1] / adj[-(win + 1)] - 1); tw += w
        if tw > 0:
            rets.append((ws / tw, sid))
    rets.sort(key=lambda x: x[0])
    n = len(rets)
    return {sid: max(1, min(99, int(round(i / (n - 1) * 98)) + 1)) for i, (_, sid) in enumerate(rets)}


def populations(as_of):
    eq = [s for s, r in secs.items() if is_equity(r["isin"] or None)]
    active = [s for s in eq if secs[s]["is_active"] == "t" and (not secs[s]["listing_date"] or load.d(secs[s]["listing_date"]) <= as_of)]
    def valid(s):
        b = series(s, as_of, 253)
        return len(b) >= 253 and (as_of - b[-1][0]).days <= 30
    A = active
    C = [s for s in active if valid(s)]
    CP = [s for s in eq if (not secs[s]["listing_date"] or load.d(secs[s]["listing_date"]) <= as_of) and valid(s)]
    i0 = SIDX[max(d for d in SESS if d <= as_of)]
    lo = SESS[i0 - 252]
    def completeness(s):
        b = series(s, as_of, 253)
        return sum(1 for x in b if x[0] >= lo) / 253
    comp = {s: completeness(s) for s in C}
    C95 = [s for s in C if comp[s] >= 0.95]
    return dict(A=A, C=C, CP=CP, C95=C95), comp


out = {"populations": {}, "is": []}
for d in ["2020-11-27", "2021-08-31", "2022-06-30", "2023-04-28", "2024-01-31", "2024-11-29", "2025-09-30", "2026-10-19"]:
    as_of = date.fromisoformat(d)
    pops, comp = populations(as_of)
    vals = sorted(comp.values())
    out["populations"][d] = dict({k: len(v) for k, v in pops.items()},
                                 C_completeness_lt_98=sum(v < .98 for v in vals), C_completeness_lt_95=sum(v < .95 for v in vals),
                                 C_completeness_lt_90=sum(v < .90 for v in vals), CP_minus_C=len(set(pops["CP"]) - set(pops["C"])),
                                 C_minus_CP=len(set(pops["C"]) - set(pops["CP"])))
    print(d, out["populations"][d])

# ---- In-Sample screener impact ----
runs = {int(r["id"]): date.fromisoformat(r["run_date"]) for r in csv.DictReader(open("data/is/runs.csv"))}
rr = defaultdict(lambda: defaultdict(dict))
for r in csv.DictReader(open("data/is/rr.csv")):
    rr[int(r["run_id"])][int(r["security_id"])][r["rule_id"]] = r
fr = defaultdict(dict)
for r in csv.DictReader(open("data/is/fr.csv")):
    fr[(int(r["run_id"]), int(r["horizon_days"]))][int(r["security_id"])] = float(r["forward_return"])


def ranked(run, R):
    rows = []
    for s, rules in rr[run].items():
        if "tt_rs_rating_min" not in rules or s not in secs or not is_equity(secs[s]["isin"] or None):
            continue
        v = R.get(s)
        gates = [g for g in rules if g.startswith("tt_") and g != "tt_rs_rating_min"]
        if v is None or v < 70 or not all(rules[g]["passed"] == "t" for g in gates):
            continue
        ov = {"rs_rating": Decimal(2) * min(max((Decimal(v) - 70) / 29, Decimal(0)), Decimal(1))}
        eng = defaultdict(lambda: [Decimal(0), Decimal(0)])
        for rid, r in sorted(rules.items()):
            eng[r["engine_id"]][0] += ov.get(rid, Decimal(r["contribution"]))
            eng[r["engine_id"]][1] += Decimal(r["weight"])
        es = {e: (a / b if b else Decimal(0)) for e, (a, b) in eng.items()}
        m = 100 * sum(Decimal(str(w)) * es.get(e, 0) for e, w in MW.items()) / sum(Decimal(str(w)) for w in MW.values())
        b_ = 100 * sum(Decimal(str(w)) * es.get(e, 0) for e, w in SW.items()) / sum(Decimal(str(w)) for w in SW.values())
        rows.append((-q4(m), -q4(b_), -v, sym[s], s, float(m)))
    rows.sort()
    return [(r[4], r[5]) for r in rows]


def spearman(xs, ys):
    def rk(v):
        o = sorted(range(len(v)), key=lambda i: v[i]); r = [0.0] * len(v)
        i = 0
        while i < len(o):
            j = i
            while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
                j += 1
            for k in range(i, j + 1):
                r[o[k]] = (i + j) / 2
            i = j + 1
        return r
    if len(xs) < 3:
        return None
    a, b = rk(xs), rk(ys)
    ma, mb = mean(a), mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** .5
    return num / den if den else None


for run, as_of in sorted(runs.items(), key=lambda x: x[1]):
    pops, _ = populations(as_of)
    row = dict(run=run, date=str(as_of))
    base = None
    for k in ("A", "C", "C95"):
        R = rs(pops[k], as_of)
        rk_ = ranked(run, R)
        top = [s for s, _ in rk_[:25]]
        base = base or set(top)
        row[f"{k}_qualified"] = len(rk_)
        row[f"{k}_top25_overlap_A"] = len(set(top) & base)
        for h in (60, 120):
            exit_i = SIDX[as_of] + h
            if SESS[exit_i] > IS_EXIT_LIMIT:
                continue
            f = fr[(run, h)]
            t = [f[s] for s in top if s in f]
            row[f"{k}_top25_fwd{h}"] = mean(t) if t else None
            row[f"{k}_top25_cov{h}"] = len(t)
            q = [(m, f[s]) for s, m in rk_ if s in f]
            row[f"{k}_ic{h}"] = spearman([x for x, _ in q], [y for _, y in q])
    out["is"].append(row)
    print(json.dumps(row))

summ = {}
for k in ("A", "C", "C95"):
    for h in (60, 120):
        v = [r[f"{k}_top25_fwd{h}"] for r in out["is"] if r.get(f"{k}_top25_fwd{h}") is not None]
        ic = [r[f"{k}_ic{h}"] for r in out["is"] if r.get(f"{k}_ic{h}") is not None]
        summ[f"{k}_fwd{h}"] = dict(runs=len(v), mean_top25=mean(v), mean_ic=mean(ic))
    summ[f"{k}_top25_overlap_A_mean"] = mean(r[f"{k}_top25_overlap_A"] for r in out["is"])
    summ[f"{k}_qualified_mean"] = mean(r[f"{k}_qualified"] for r in out["is"])
# paired difference C - A at 120d
pairs = [(r["C_top25_fwd120"] - r["A_top25_fwd120"]) for r in out["is"] if r.get("C_top25_fwd120") is not None]
summ["C_minus_A_fwd120"] = dict(n=len(pairs), mean=mean(pairs), positive=sum(p > 0 for p in pairs), negative=sum(p < 0 for p in pairs))
out["summary"] = summ
print(json.dumps(summ, indent=1))
json.dump(out, open("rs_ref.json", "w"), indent=1)
