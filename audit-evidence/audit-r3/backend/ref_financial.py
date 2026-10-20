"""Independent financial reference checks for the Round 3 audit.

Standalone: imports no momentum25 code. It reads the restored audit copy
(read-only SELECTs) and the API that runs against that copy, recomputes
reference values from the published formulas (IMPLEMENTATION_SPEC §8), and
compares them with what production stored or served.

Usage:
    python ref_financial.py <postgres dsn> <api base url> <run_id> <as_of>
"""

from __future__ import annotations

import asyncio
import json
import math
import sys
import urllib.request
from collections import defaultdict
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal

import asyncpg

SYMBOLS = ["RELIANCE", "TCS", "MCX", "GOLDIAM", "TRENT"]
RS_WEIGHTS = {63: 0.4, 126: 0.2, 189: 0.2, 252: 0.2}
WINDOW = 277  # max(200 + 22, 252, 50) + 25, the snapshot read window


def get(url: str) -> dict:
    with urllib.request.urlopen(url) as r:  # noqa: S310 - loopback audit API
        return json.loads(r.read())


def q4(x: float | None) -> Decimal | None:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    return Decimal(f"{x:.4f}")


# ---------- reference formulas (written from the spec, not from the code) ----------


def sma(xs, n):
    return sum(xs[-n:]) / n if len(xs) >= n else None


def ema_series(xs, n):
    # Production seeds with the first value (documented deviation from spec §8,
    # which says SMA seed). Both are computed; the first-value one is compared.
    k = 2 / (n + 1)
    out, e = [], None
    for x in xs:
        e = x if e is None else x * k + e * (1 - k)
        out.append(e)
    return out


def wilder(values, n):
    out = [None] * len(values)
    if len(values) < n:
        return out
    avg = sum(values[:n]) / n
    out[n - 1] = avg
    for i in range(n, len(values)):
        avg = (avg * (n - 1) + values[i]) / n
        out[i] = avg
    return out


def rsi_series(closes, n=14):
    d = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    g = wilder([max(x, 0.0) for x in d], n)
    lo = wilder([max(-x, 0.0) for x in d], n)
    out = [None]
    for a, b in zip(g, lo, strict=True):
        if a is None:
            out.append(None)
        elif b == 0:
            out.append(50.0 if a == 0 else 100.0)
        else:
            out.append(100 - 100 / (1 + a / b))
    return out


def true_ranges(h, l, c):
    return [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])) for i in range(1, len(c))]


def atr_series(h, l, c, n=14):
    return [None] + wilder(true_ranges(h, l, c), n)


def adx_series(h, l, c, n=14):
    up = [h[i] - h[i - 1] for i in range(1, len(h))]
    dn = [l[i - 1] - l[i] for i in range(1, len(l))]
    pdm = [u if u > v and u > 0 else 0.0 for u, v in zip(up, dn, strict=True)]
    mdm = [v if v > u and v > 0 else 0.0 for u, v in zip(up, dn, strict=True)]
    tr = true_ranges(h, l, c)
    sp, sm, st = wilder(pdm, n), wilder(mdm, n), wilder(tr, n)
    dx = []
    for a, b, t in zip(sp, sm, st, strict=True):
        if a is None:
            continue
        pdi, mdi = 100 * a / t, 100 * b / t
        dx.append(0.0 if pdi + mdi == 0 else 100 * abs(pdi - mdi) / (pdi + mdi))
    adx = wilder(dx, n)
    return [None] * (len(c) - len(adx)) + adx


def macd_series(c, fast=12, slow=26, sig=9):
    line = [a - b for a, b in zip(ema_series(c, fast), ema_series(c, slow), strict=True)]
    signal = ema_series(line, sig)
    hist = [a - b for a, b in zip(line, signal, strict=True)]
    cut = slow + sig - 1
    mask = lambda s: [None] * cut + s[cut:]  # noqa: E731
    return mask(line), mask(signal), mask(hist)


def factors_for(dates, actions):
    """Backward factor: product of ratios of every priced action with ex_date > d."""
    out = {}
    for d in dates:
        f = Decimal(1)
        for ex, ratio in actions:
            if ratio is not None and ex > d:
                f *= ratio
        out[d] = f
    return out


async def main() -> None:
    dsn, api, run_id, as_of = sys.argv[1], sys.argv[2], int(sys.argv[3]), date.fromisoformat(sys.argv[4])
    con = await asyncpg.connect(dsn)
    await con.execute("SET default_transaction_read_only = on")
    report: dict = {"as_of": as_of.isoformat(), "run_id": run_id}

    # ---- 1. Adjustment factors, universe-wide ----
    acts = defaultdict(list)
    for r in await con.fetch(
        "select security_id, ex_date, type, ratio from corporate_actions"
    ):
        if r["ratio"] is not None:
            acts[r["security_id"]].append((r["ex_date"], r["ratio"]))
    div_with_ratio = await con.fetchval(
        "select count(*) from corporate_actions where ratio is not null and type not in ('split','bonus')"
    )
    mism, checked, worst = 0, 0, []
    for sid, a in acts.items():
        rows = await con.fetch(
            "select date, adj_factor from ohlcv_daily where security_id=$1 order by date", sid
        )
        exp = factors_for([r["date"] for r in rows], a)
        for r in rows:
            checked += 1
            e = exp[r["date"]]
            if abs(r["adj_factor"] - e) > Decimal("0.00000002") * max(e, Decimal(1)):
                mism += 1
                if len(worst) < 15:
                    worst.append((sid, r["date"].isoformat(), str(r["adj_factor"]), str(e)))
    unit_ok = await con.fetchval(
        "select count(*) from ohlcv_daily o where adj_factor<>1 and not exists "
        "(select 1 from corporate_actions c where c.security_id=o.security_id and c.ratio is not null and c.ex_date>o.date)"
    )
    report["adjustment_factors"] = {
        "securities_with_priced_actions": len(acts),
        "bars_checked": checked,
        "factor_mismatches": mism,
        "mismatch_examples": worst,
        "non_unit_factor_without_later_action": unit_ok,
        "non_split_bonus_actions_with_ratio": div_with_ratio,
    }

    # ---- 2. Indicators for named symbols vs the API ----
    ind = {}
    for sym in SYMBOLS:
        sid = await con.fetchval("select id from securities where symbol=$1 and is_active", sym)
        rows = await con.fetch(
            "select date, open, high, low, close, volume, adj_factor, adj_close from ohlcv_daily "
            "where security_id=$1 and date<=$2 order by date desc limit $3",
            sid, as_of, WINDOW,
        )
        rows = list(reversed(rows))
        f = [float(r["adj_factor"]) for r in rows]
        o = [float(r["open"]) * k for r, k in zip(rows, f, strict=True)]
        h = [float(r["high"]) * k for r, k in zip(rows, f, strict=True)]
        lo = [float(r["low"]) * k for r, k in zip(rows, f, strict=True)]
        c = [float(r["close"]) * k for r, k in zip(rows, f, strict=True)]
        v = [r["volume"] / k for r, k in zip(rows, f, strict=True)]
        ref = {
            "sma50": sma(c, 50), "sma150": sma(c, 150), "sma200": sma(c, 200),
            "high_52w": max(h[-252:]), "low_52w": min(lo[-252:]),
            "adr_pct": sum(a / b - 1 for a, b in zip(h[-20:], lo[-20:], strict=True)) / 20 * 100,
            "avg_volume50": sum(v[-50:]) / 50,
            "rel_volume_spec": v[-1] / (sum(v[-50:]) / 50),
            "rel_volume_impl_49d": v[-1] / (sum(v[-50:-1]) / 49),
        }
        s200 = [sma(c[: i + 1], 200) for i in range(len(c))]
        ref["sma200_slope_pct"] = (s200[-1] / s200[-23] - 1) * 100
        ref["pct_above_low_52w"] = (c[-1] - ref["low_52w"]) / ref["low_52w"] * 100
        ref["pct_below_high_52w"] = (ref["high_52w"] - c[-1]) / ref["high_52w"] * 100
        series_ref = {
            "rsi14": rsi_series(c), "atr14": atr_series(h, lo, c), "adx14": adx_series(h, lo, c),
        }
        ml, ms, mh = macd_series(c)
        series_ref.update(macd_line=ml, macd_signal=ms, macd_histogram=mh)
        api_series = get(f"{api}/stocks/{sym}/indicators/series")["bars"]
        by_date = {b["date"]: b for b in api_series}
        diffs = defaultdict(lambda: [0, 0, 0.0])
        for i, r in enumerate(rows):
            b = by_date.get(r["date"].isoformat())
            if b is None:
                continue
            for k, s in series_ref.items():
                mine = q4(s[i])
                theirs = None if b.get(k) is None else Decimal(b[k])
                d = diffs[k]
                d[0] += 1
                if mine != theirs:
                    if mine is None or theirs is None:
                        d[1] += 1
                    elif abs(mine - theirs) > Decimal("0.0001"):
                        d[1] += 1
                        d[2] = max(d[2], float(abs(mine - theirs)))
        live = get(f"{api}/stocks/{sym}/live")["explanation"]["rule_explanations"]
        actual = {x["rule_id"]: x for x in live}
        checks = {
            "tt_above_52w_low": ref["pct_above_low_52w"],
            "tt_near_52w_high": ref["pct_below_high_52w"],
            "tt_sma200_uptrend": ref["sma200_slope_pct"],
            "tt_close_above_sma50": c[-1],
            "tt_sma150_above_sma200": ref["sma150"],
            "risk_atr": ref["adr_pct"],
        }
        rule_cmp = {
            k: {"ref": str(q4(val)), "api": actual[k]["actual_value"],
                "match": abs(Decimal(actual[k]["actual_value"]) - q4(val)) <= Decimal("0.0001")}
            for k, val in checks.items() if k in actual
        }
        sma_text = actual["tt_sma_stack"]["explanation"]
        ind[sym] = {
            "bars": len(rows),
            "first_bar": rows[0]["date"].isoformat(),
            "reference": {k: str(q4(val)) for k, val in ref.items()},
            "series_compare": {k: {"compared": d[0], "mismatch": d[1], "max_abs_diff": d[2]} for k, d in diffs.items()},
            "rule_value_compare": rule_cmp,
            "api_sma_stack_text": sma_text,
            "adj_close_vs_close_x_factor_max_abs": max(
                (abs(float(r["adj_close"]) - float(r["close"]) * float(r["adj_factor"])) for r in rows if r["adj_close"] is not None),
                default=0.0,
            ),
        }
    report["indicators"] = ind

    # ---- 3. RS ratings over the run universe ----
    secs = await con.fetch("select id, symbol, isin from securities where is_active order by id")
    eq = [s for s in secs if s["isin"] is None or not s["isin"].strip().upper().startswith("INF")]
    rets = []
    for s in eq:
        rows = await con.fetch(
            "select coalesce(adj_close, close) px from ohlcv_daily where security_id=$1 and date<=$2 "
            "order by date desc limit $3", s["id"], as_of, max(RS_WEIGHTS) + 5,
        )
        px = [float(r["px"]) for r in reversed(rows)]
        if len(px) < 2:
            continue
        ws, tw = 0.0, 0.0
        for p, w in RS_WEIGHTS.items():
            win = min(p, len(px) - 1)
            prior = px[-(win + 1)]
            if prior <= 0:
                continue
            ws += w * (px[-1] / prior - 1)
            tw += w
        if tw > 0:
            rets.append((s["id"], s["symbol"], ws / tw))
    rets.sort(key=lambda t: t[2])
    n = len(rets)
    mine = {sid: max(1, min(99, int(round(i / (n - 1) * 98)) + 1)) for i, (sid, _, _) in enumerate(rets)}
    ties = sum(1 for i in range(1, n) if rets[i][2] == rets[i - 1][2])
    stored = {
        r["security_id"]: int(r["raw_value"])
        for r in await con.fetch(
            "select security_id, raw_value from rule_results where run_id=$1 and rule_id='tt_rs_rating_min'", run_id
        )
    }
    diff = [(sid, mine.get(sid), v) for sid, v in stored.items() if mine.get(sid) != v]
    # Spec §8: rank across the *eligible* universe only.
    elig = {r["security_id"] for r in await con.fetch(
        "select security_id from universe_membership where run_id=$1 and eligible", run_id)}
    er = [t for t in rets if t[0] in elig]
    ne = len(er)
    spec = {sid: max(1, min(99, int(round(i / (ne - 1) * 98)) + 1)) for i, (sid, _, _) in enumerate(er)}
    cross = lambda m: sum(1 for sid, v in stored.items() if (v >= 70) != (m.get(sid, 0) >= 70))  # noqa: E731
    report["rs_ratings"] = {
        "universe_ranked": n,
        "exact_return_ties": ties,
        "stored_scored": len(stored),
        "mismatches_vs_stored": len(diff),
        "mismatch_examples": diff[:10],
        "spec_eligible_universe_size": ne,
        "spec_variant_rating_changes": sum(1 for sid, v in stored.items() if spec.get(sid) != v),
        "spec_variant_rs70_crossings": cross(spec),
    }

    # ---- 4. Weekly / monthly aggregation vs API ----
    agg = {}
    for sym in SYMBOLS:
        sid = await con.fetchval("select id from securities where symbol=$1 and is_active", sym)
        rows = await con.fetch(
            "select date, open, high, low, close, volume, adj_factor from ohlcv_daily where security_id=$1 order by date", sid
        )
        out = {}
        for period, key in (("1W", lambda d: tuple(d.isocalendar())[:2]), ("1M", lambda d: (d.year, d.month))):
            groups = defaultdict(list)
            for r in rows:
                groups[key(r["date"])].append(r)
            ref = {}
            for g in groups.values():
                fq = [r["adj_factor"] for r in g]
                p = lambda col: [(r[col] * k).quantize(Decimal("0.0001")) for r, k in zip(g, fq, strict=True)]  # noqa: E731
                ref[g[-1]["date"].isoformat()] = (
                    p("open")[0], max(p("high")), min(p("low")), p("close")[-1],
                    sum(round(Decimal(r["volume"]) / k) for r, k in zip(g, fq, strict=True)),
                )
            bars = get(f"{api}/securities/{sym}/ohlcv?interval={period}")["bars"]
            bad = []
            for b in bars:
                e = ref.get(b["date"])
                got = (Decimal(b["open"]), Decimal(b["high"]), Decimal(b["low"]), Decimal(b["close"]), int(b["volume"]))
                if e is None or any(abs(Decimal(x) - Decimal(y)) > Decimal("0.0001") for x, y in zip(e[:4], got[:4], strict=True)) or int(e[4]) != got[4]:
                    bad.append((b["date"], [str(x) for x in (e or ())], [str(x) for x in got]))
            out[period] = {"api_bars": len(bars), "ref_bars": len(ref), "mismatches": len(bad), "examples": bad[:3]}
        agg[sym] = out
    report["period_aggregation"] = agg

    # ---- 5. Gates, scores, ranks for the stored run ----
    rr = await con.fetch(
        "select security_id, engine_id, rule_id, passed, raw_value, threshold, operator, weight, contribution "
        "from rule_results where run_id=$1", run_id
    )
    ops = {">=": lambda a, b: a >= b, ">": lambda a, b: a > b, "<=": lambda a, b: a <= b, "<": lambda a, b: a < b}
    op_mismatch, boundary = 0, defaultdict(int)
    by_sec = defaultdict(list)
    for r in rr:
        by_sec[r["security_id"]].append(r)
        fn = ops.get(r["operator"])
        if fn is not None and r["engine_id"] in ("trend_template", "volume_accumulation") and r["rule_id"] != "vol_accumulation_days":
            if fn(r["raw_value"], r["threshold"]) != r["passed"]:
                op_mismatch += 1
            if r["raw_value"] == r["threshold"]:
                boundary[r["rule_id"]] += 1
    cfg = json.load(open(sys.argv[5])) if len(sys.argv) > 5 else None
    mw = cfg["scoring"]["momentum_weights"] if cfg else {}
    bw = cfg["scoring"]["buy_setup_weights"] if cfg else {}
    res = {r["security_id"]: r for r in await con.fetch(
        "select security_id, rank, momentum_score, buy_setup_score, hard_filters_passed from screening_results where run_id=$1", run_id)}
    gate_mm, mom_mm, bs_mm, rank_mm = 0, 0, 0, 0
    max_mom = Decimal(0)
    scored = []
    for sid, rows in by_sec.items():
        tt = all(r["passed"] for r in rows if r["engine_id"] == "trend_template")
        liq = all(r["passed"] for r in rows if r["rule_id"] == "vol_liquidity_min")
        gate = tt and liq
        es = defaultdict(lambda: [Decimal(0), Decimal(0)])
        for r in rows:
            es[r["engine_id"]][0] += r["contribution"]
            es[r["engine_id"]][1] += r["weight"]
        def score(weights):
            tw = sum(Decimal(str(weights.get(e, 0))) for e in es if e != "trend_template")
            ws = sum(Decimal(str(weights.get(e, 0))) * (v[0] / v[1] if v[1] else Decimal(0)) for e, v in es.items() if e != "trend_template")
            return (Decimal(100) * ws / tw).quantize(Decimal("0.0001"), ROUND_HALF_EVEN) if tw else Decimal(0)
        m, b = score(mw), score(bw)
        s = res[sid]
        gate_mm += gate != s["hard_filters_passed"]
        if abs(m - s["momentum_score"]) > Decimal("0.0005"):
            mom_mm += 1
        max_mom = max(max_mom, abs(m - s["momentum_score"]))
        bs_mm += abs(b - s["buy_setup_score"]) > Decimal("0.0005")
        rs = next((int(r["raw_value"]) for r in rows if r["rule_id"] == "rs_rating"), 0)
        if s["hard_filters_passed"]:
            scored.append((-s["momentum_score"], -s["buy_setup_score"], -rs, sid))
    scored.sort()
    for i, t in enumerate(scored, start=1):
        rank_mm += res[t[3]]["rank"] != i
    # How many exact (momentum, buy_setup, rs) ties are broken by security_id?
    tie_groups = sum(1 for i in range(1, len(scored)) if scored[i][:3] == scored[i - 1][:3])
    report["gates_scores_ranks"] = {
        "rule_rows": len(rr),
        "operator_recompute_mismatches": op_mismatch,
        "exact_boundary_rows": dict(boundary),
        "hard_filter_mismatches": gate_mm,
        "momentum_score_mismatches_gt_0.0005": mom_mm,
        "momentum_score_max_abs_diff": str(max_mom),
        "buy_setup_mismatches_gt_0.0005": bs_mm,
        "qualified": len(scored),
        "rank_mismatches": rank_mm,
        "rank_ties_broken_by_security_id": tie_groups,
    }
    await con.close()
    print(json.dumps(report, indent=2, default=str))


asyncio.run(main())
