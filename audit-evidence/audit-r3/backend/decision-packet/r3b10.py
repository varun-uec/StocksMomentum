"""R3-B-10: quantify the four spec differences on run #149 (2026-10-19).

Independent of the screening code: RS, rel_volume, EMA and the score
recomposition are re-implemented from IMPLEMENTATION_SPEC §8/§10 and checked
against the stored run first. Only is_equity() (the universe selector the run
uses) is imported from production.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal

import load
from momentum25.domain.value_objects.instrument import is_equity

AS_OF = date(2026, 10, 19)
D = "data/"
MW = {"relative_strength": 2, "volume_accumulation": 1, "pattern": 1,
      "breakout": 1.5, "momentum_quality": 1, "risk": 0.5}
SW = {"breakout": 3, "volume_accumulation": 2, "pattern": 1.5, "risk": 1.5,
      "relative_strength": 1}
RSW = {63: 0.4, 126: 0.2, 189: 0.2, 252: 0.2}

bars = load.load_bars()
secs = {int(r["id"]): r for r in load.securities()}
sym = {s: r["symbol"] for s, r in secs.items()}
um = {int(r["security_id"]): (r["eligible"] == "t", r["reason"]) for r in csv.DictReader(open(D + "um149.csv"))}
rr = defaultdict(dict)
for r in csv.DictReader(open(D + "rr149.csv")):
    rr[int(r["security_id"])][r["rule_id"]] = r
sr = {int(r["security_id"]): r for r in csv.DictReader(open(D + "sr149.csv"))}


def upto(sid, n=None):
    rows = [b for b in bars.get(sid, []) if b[0] <= AS_OF]
    return rows[-n:] if n else rows


# ---------- 1. RS universe ----------
# Last 257 bars per security from ohlcv_daily (the run's SqlOHLCVRepository).
rs_bars = defaultdict(list)
for r in csv.DictReader(open(D + "rs_bars.csv")):
    rs_bars[int(r["security_id"])].append((Decimal(r["close"]), Decimal(r["adj_close"]) if r["adj_close"] else None))

def rs_ratings(universe):
    rets = []
    for sid in universe:
        b = rs_bars.get(sid, [])[-(max(RSW) + 5):]
        if len(b) < 2:
            continue
        adj = [float(x[1] if x[1] is not None else x[0]) for x in b]
        ws = tw = 0.0
        for p, w in RSW.items():
            win = min(p, len(b) - 1)
            if win <= 0 or adj[-(win + 1)] <= 0:
                continue
            ws += w * (adj[-1] / adj[-(win + 1)] - 1)
            tw += w
        if tw > 0:
            rets.append((sym[sid], ws / tw, sid))
    rets.sort(key=lambda x: x[1])
    n = len(rets)
    return {sid: max(1, min(99, int(round(i / (n - 1) * 98)) + 1)) for i, (_, _, sid) in enumerate(rets)}, n


active_eq = [s for s, r in secs.items() if r["is_active"] == "t" and is_equity(r["isin"] or None)]
cur, n_cur = rs_ratings(active_eq)
scored = sorted(rr)
mism = [s for s in scored if Decimal(rr[s]["tt_rs_rating_min"]["raw_value"]) != cur.get(s)]
eligible = [s for s, (e, _) in um.items() if e]
alt, n_alt = rs_ratings(eligible)
changed = [s for s in scored if cur[s] != alt.get(s)]
cross = [s for s in scored if (cur[s] >= 70) != (alt[s] >= 70)]
# composition of the current RS universe by eligibility reason
reason_mix = defaultdict(int)
for s in active_eq:
    if s in cur:
        reason_mix[um.get(s, (None, "not_in_run_universe"))[1] or "eligible"] += 1


# ---------- score recomposition ----------
def q4(x):
    return Decimal(x).quantize(Decimal("0.0001"), rounding=ROUND_HALF_EVEN)


def scores(sid, override):
    """momentum and buy-setup from stored contributions with rule overrides {rule_id: contribution}."""
    eng = defaultdict(lambda: [Decimal(0), Decimal(0)])
    for rid, r in sorted(rr[sid].items()):
        c = override.get(rid, Decimal(r["contribution"]))
        eng[r["engine_id"]][0] += c
        eng[r["engine_id"]][1] += Decimal(r["weight"])
    es = {e: (v[0] / v[1] if v[1] else Decimal(0)) for e, v in eng.items()}
    # trend_template is a gate engine: excluded from both scores (scoring_engine.py)
    m = 100 * sum(Decimal(str(w)) * es.get(e, 0) for e, w in MW.items()) / sum(Decimal(str(w)) for w in MW.values())
    b = 100 * sum(Decimal(str(w)) * es.get(e, 0) for e, w in SW.items()) / sum(Decimal(str(w)) for w in SW.values())
    return m, b


GATE = [k for k in rr[scored[0]] if k.startswith("tt_")]


def gate_pass(sid, rs_value):
    others = all(rr[sid][g]["passed"] == "t" for g in GATE if g != "tt_rs_rating_min")
    return others and rs_value >= 70


gate_check = sum(gate_pass(s, cur[s]) == (sr[s]["hard_filters_passed"] == "t") for s in scored)
if gate_check != len(scored):  # liquidity rule may be a gate too
    GATE.append("vol_liquidity_min")
    gate_check = sum(gate_pass(s, cur[s]) == (sr[s]["hard_filters_passed"] == "t") for s in scored)


def rs_override(v):
    return {"tt_rs_rating_min": Decimal("1.5") if v >= 70 else Decimal(0),
            "rs_rating": Decimal(2) * min(max((Decimal(v) - 70) / 29, Decimal(0)), Decimal(1))}


def ranking(rs_map, override_fn, tie="id"):
    rows = []
    for s in scored:
        rs = rs_map[s]
        if not gate_pass(s, rs):
            continue
        m, b = scores(s, override_fn(s))
        key_tail = s if tie == "id" else sym[s]
        rows.append((-q4(m), -q4(b), -rs, key_tail, s))
    rows.sort()
    return [r[-1] for r in rows], {r[-1]: (r[0], r[1]) for r in rows}


base_rank, base_sc = ranking(cur, lambda s: {})
repro = sum(1 for i, s in enumerate(base_rank, 1) if str(i) == sr[s]["rank"])
max_score_diff = max(abs(-base_sc[s][0] - Decimal(sr[s]["momentum_score"])) for s in base_rank)
alt_rank, _ = ranking(alt, lambda s: rs_override(alt[s]))
rs_result = dict(
    rs_universe_current=n_cur, rs_universe_eligible=n_alt,
    current_reproduces_stored_ratings=len(mism) == 0, mismatches=len(mism),
    ratings_changed=len(changed), cross_70=len(cross),
    cross_up=sum(1 for s in cross if alt[s] >= 70), cross_down=sum(1 for s in cross if alt[s] < 70),
    mean_abs_change=sum(abs(cur[s] - alt[s]) for s in scored) / len(scored),
    current_universe_mix=dict(reason_mix),
    gate_rules=GATE, gate_reproduced=f"{gate_check}/{len(scored)}",
    ranks_reproduced=f"{repro}/{len(base_rank)}", max_momentum_diff_vs_stored=str(max_score_diff),
    passing_current=len(base_rank), passing_eligible_rs=len(alt_rank),
    top25_overlap=len(set(base_rank[:25]) & set(alt_rank[:25])),
    top25_entered=[sym[s] for s in alt_rank[:25] if s not in base_rank[:25]],
    top25_left=[sym[s] for s in base_rank[:25] if s not in alt_rank[:25]],
    top1_current=sym[base_rank[0]], top1_eligible=sym[alt_rank[0]],
)


# ---------- 2. rel_volume ----------
def vol_adj(b):
    f = float(b[6] or 1)
    return b[5] / f


rv = {}
for s in scored:
    b = upto(s, 277)
    v = [vol_adj(x) for x in b]
    if len(v) < 52:
        continue
    code = v[-1] / (sum(v[-50:-1]) / 49)  # implemented: 49 prior sessions
    spec = v[-1] / (sum(v[-50:]) / 50)  # spec §8: avg_volume50 includes today
    prior50 = v[-1] / (sum(v[-51:-1]) / 50)  # docstring intent: 50 prior sessions
    rv[s] = (code, spec, prior50)
stored_ok = sum(1 for s, (c, _, _) in rv.items() if abs(Decimal(str(c)) - Decimal(rr[s]["vol_breakout_confirm"]["raw_value"])) < Decimal("0.0001"))
TH = 1.4


def rv_override(i):
    return lambda s: {"vol_breakout_confirm": Decimal(str(min(rv[s][i] / TH, 1.0))) if s in rv else Decimal(rr[s]["vol_breakout_confirm"]["contribution"])}


rv_spec_rank, _ = ranking(cur, rv_override(1))
rv_p50_rank, _ = ranking(cur, rv_override(2))
relvol_result = dict(
    names=len(rv), stored_equals_49_prior=stored_ok,
    pass_flips_spec=sum(1 for c, s_, _ in rv.values() if (c >= TH) != (s_ >= TH)),
    pass_flips_prior50=sum(1 for c, _, p in rv.values() if (c >= TH) != (p >= TH)),
    max_rel_diff_spec=max(abs(s_ / c - 1) for c, s_, _ in rv.values() if c),
    max_rel_diff_prior50=max(abs(p / c - 1) for c, _, p in rv.values() if c),
    top25_overlap_spec=len(set(base_rank[:25]) & set(rv_spec_rank[:25])),
    top25_overlap_prior50=len(set(base_rank[:25]) & set(rv_p50_rank[:25])),
    rank_changes_spec=sum(1 for a, b in zip(base_rank, rv_spec_rank) if a != b),
    rank_changes_prior50=sum(1 for a, b in zip(base_rank, rv_p50_rank) if a != b),
)


# ---------- 3. EMA seed ----------
def ema(xs, n, seed):
    k = 2 / (n + 1)
    out = [None] * len(xs)
    if seed == "first":
        e = xs[0]
        out[0] = e
        start = 1
    else:
        if len(xs) < n:
            return out
        e = sum(xs[:n]) / n
        out[n - 1] = e
        start = n
    for i in range(start, len(xs)):
        e = xs[i] * k + e * (1 - k)
        out[i] = e
    return out


def macd(xs, seed):
    f, s = ema(xs, 12, seed), ema(xs, 26, seed)
    line = [a - b if a is not None and b is not None else None for a, b in zip(f, s)]
    first = next(i for i, v in enumerate(line) if v is not None)
    sig = [None] * first + ema(line[first:], 9, seed)
    return line, sig


ema_last = defaultdict(int)
series_max_rel = 0.0
series_rows_differ = 0
series_rows = 0
names_ema = 0
for s in scored:
    b = upto(s, 277)
    if len(b) < 60:
        continue
    names_ema += 1
    c = [float(x[4]) * float(x[6] or 1) for x in b]
    for n in (10, 21):
        a, bb = ema(c, n, "first")[-1], ema(c, n, "sma")[-1]
        if round(a, 4) != round(bb, 4):
            ema_last[f"ema{n}"] += 1
    (l1, s1), (l2, s2) = macd(c, "first"), macd(c, "sma")
    if round(l1[-1], 4) != round(l2[-1], 4) or round(s1[-1], 4) != round(s2[-1], 4):
        ema_last["macd_last_bar"] += 1
    for i in range(34, len(c)):  # production withholds the first slow+signal-1 bars
        if s2[i] is None:
            continue
        series_rows += 1
        if round(l1[i], 4) != round(l2[i], 4):
            series_rows_differ += 1
        series_max_rel = max(series_max_rel, abs(l1[i] - l2[i]) / c[i])
ema_result = dict(names=names_ema, last_bar_differences_at_4dp=dict(ema_last),
                  macd_series_rows=series_rows, macd_series_rows_differ_4dp=series_rows_differ,
                  macd_series_max_diff_as_pct_of_price=series_max_rel * 100)

# ---------- 4. tie-break ----------
passing = list(csv.DictReader(open(D + "sr_all_passing.csv")))
by_run = defaultdict(list)
for r in passing:
    by_run[r["run_id"]].append(r)
ties = []
for run, rows in by_run.items():
    seen = defaultdict(list)
    for r in rows:
        seen[(r["momentum_score"], r["buy_setup_score"], r["rs"])].append(r)
    for k, v in seen.items():
        if len(v) > 1:
            ids = sorted(v, key=lambda r: int(r["security_id"]))
            syms = sorted(v, key=lambda r: r["symbol"])
            ties.append((run, k, [r["symbol"] for r in v], ids != syms))
ordered = sorted(secs)
inv = sum(1 for a, b in zip(ordered, ordered[1:]) if sym[a] > sym[b])
tie_result = dict(runs=len(by_run), passing_rows=len(passing), tied_groups=len(ties),
                  tied_groups_where_order_differs=sum(1 for t in ties if t[3]), examples=ties[:5],
                  adjacent_id_pairs_out_of_symbol_order=inv, securities=len(ordered))
_, _ = ranking(cur, lambda s: {}, tie="symbol")
sym_rank, _ = ranking(cur, lambda s: {}, tie="symbol")
tie_result["run149_rank_changes_with_symbol_tiebreak"] = sum(1 for a, b in zip(base_rank, sym_rank) if a != b)

out = dict(rs=rs_result, rel_volume=relvol_result, ema=ema_result, tie_break=tie_result)
json.dump(out, open("r3b10.json", "w"), indent=1, default=str)
print(json.dumps(out, indent=1, default=str))
