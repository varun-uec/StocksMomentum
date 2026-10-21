"""Independent recompute of forward returns: raw SQL + exchange_calendars only."""
import asyncio, sys, random, bisect
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_EVEN
import asyncpg, exchange_calendars as xc

DSN = sys.argv[1]; N = int(sys.argv[2])
async def main():
    cal = xc.get_calendar("XBOM")
    con = await asyncpg.connect(DSN)
    runs = await con.fetch("select id, run_date from screening_runs where data_version like '%:engine2-monthly%' and status='COMPLETED' order by id")
    bench = {r['date']: r['close'] for r in await con.fetch("select date, close from benchmark_index_daily where index_code='NIFTY500'")}
    bd = sorted(bench)
    def nb(d):
        for o in range(10):
            c = d - timedelta(days=o)
            if c in bench: return bench[c]
    rnd = random.Random(7); bad = 0; checked = 0; miss = 0
    q4 = Decimal("0.0001")
    for run in runs:
        t = run['run_date']
        sess = [s.date() for s in cal.sessions_in_range(t + timedelta(days=1), t + timedelta(days=500))]
        rows = await con.fetch("select * from forward_returns where run_id=$1 and horizon_basis='sessions'", run['id'])
        for r in rnd.sample(rows, min(N, len(rows))):
            h = r['horizon_days']; E = sess[h-1]
            bars = await con.fetch("select date, close*adj_factor as a from ohlcv_daily where security_id=$1 and date<=$2 order by date desc limit 1", r['security_id'], t)
            ex = await con.fetch("select date, close*adj_factor as a from ohlcv_daily where security_id=$1 and date>$2 and date<=$3 order by date", r['security_id'], t, E)
            entry = bars[0]['a']
            if ex:
                last = ex[-1]; stale = h - bisect.bisect_right(sess[:h], last['date']); px = last['a']
            else:
                stale, px = h, entry
            fr = (Decimal(px)/Decimal(entry) - 1).quantize(q4, ROUND_HALF_EVEN)
            be, bx = nb(t), nb(E)
            br = (bx/be - 1).quantize(q4, ROUND_HALF_EVEN) if be and bx else None
            ok = abs(fr - r['forward_return']) <= q4 and r['exit_date']==E and r['exit_stale_sessions']==stale \
                 and ((br is None and r['benchmark_return'] is None) or (br is not None and r['benchmark_return'] is not None and abs(br - r['benchmark_return']) <= q4))
            mx = min(r['forward_mae'], 0); mfe = max([(Decimal(b['a'])/Decimal(entry)-1) for b in ex] or [Decimal(0)])
            ok = ok and abs(mfe.quantize(q4) - r['forward_mfe']) <= q4
            checked += 1
            if not ok:
                bad += 1; print("MISMATCH", run['id'], r['security_id'], h, fr, r['forward_return'], r['exit_date'], E, stale, r['exit_stale_sessions'], br, r['benchmark_return'])
    print("checked", checked, "mismatches", bad)
asyncio.run(main())
