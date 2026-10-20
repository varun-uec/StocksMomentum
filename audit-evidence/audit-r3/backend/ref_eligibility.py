"""Independent universe-eligibility reference (no momentum25 import).

Rules (strategy universe block + ADD/spec, as declared): equities only (ISIN not INF*);
277 bars for indicators (SMA200 + 22-session slope + 25 buffer); stale if the last bar
is more than 30 days before D; a bar on D; >= 252 prior sessions; 50 trailing real
turnovers with mean >= 1e7 INR; close >= 20 INR. Compares with universe_membership.
Usage: python ref_eligibility.py <dsn> <run_id> <D>
"""
import asyncio
import sys
from collections import Counter
from datetime import date
from decimal import Decimal

import asyncpg


async def main() -> None:
    dsn, run_id, d = sys.argv[1], int(sys.argv[2]), date.fromisoformat(sys.argv[3])
    con = await asyncpg.connect(dsn)
    await con.execute("SET default_transaction_read_only = on")
    stored = {r["security_id"]: (r["eligible"], r["reason"]) for r in await con.fetch(
        "select security_id, eligible, reason from universe_membership where run_id=$1", run_id)}
    secs = await con.fetch("select id, isin from securities where is_active order by id")
    mine, diffs, boundary = {}, [], Counter()
    for s in secs:
        if s["isin"] and s["isin"].strip().upper().startswith("INF"):
            continue
        rows = await con.fetch(
            "select date, close, turnover_value from ohlcv_daily where security_id=$1 and date<=$2 "
            "order by date desc limit 277", s["id"], d)
        rows = list(reversed(rows))
        if len(rows) < 277:
            v = (False, "insufficient_history")
        elif (d - rows[-1]["date"]).days > 30:
            v = (False, "stale_data")
        elif rows[-1]["date"] != d:
            v = (False, "no_bar_on_trading_date")
        else:
            ctx = rows[-275:]
            t = [r["turnover_value"] for r in ctx][-50:]
            close = rows[-1]["close"]
            if len(ctx) - 1 < 252:
                v = (False, "insufficient_history")
            elif len(t) < 50 or any(x is None for x in t):
                v = (False, "insufficient_turnover_data")
            elif close < 20:
                v = (False, "close_below_floor")
            elif sum(t, Decimal(0)) / 50 < Decimal(10_000_000):
                v = (False, "below_liquidity_floor")
            else:
                v = (True, None)
            if close == 20:
                boundary["close == 20"] += 1
            if len(t) == 50 and None not in t and sum(t, Decimal(0)) / 50 == Decimal(10_000_000):
                boundary["avg turnover == 1e7"] += 1
        mine[s["id"]] = v
        if stored.get(s["id"]) != v:
            diffs.append((s["id"], v, stored.get(s["id"])))
    print({"universe": len(mine), "stored_rows": len(stored),
           "eligible_ref": sum(1 for v in mine.values() if v[0]),
           "eligible_stored": sum(1 for v in stored.values() if v[0]),
           "mismatches": len(diffs), "examples": diffs[:10],
           "reasons_ref": Counter(v[1] for v in mine.values()),
           "exact_boundary_cases": dict(boundary)})
    await con.close()


asyncio.run(main())
