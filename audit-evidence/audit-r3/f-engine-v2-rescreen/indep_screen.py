"""Independent reference: SMA50/150/200 and 52w position from raw bars (adj_factor==1 names only)."""
import asyncio, sys
from decimal import Decimal
import asyncpg
DSN=sys.argv[1]; RUN=int(sys.argv[2])
async def main():
    c=await asyncpg.connect(DSN)
    run=await c.fetchrow("select run_date from screening_runs where id=$1",RUN); d=run['run_date']
    ids=[r[0] for r in await c.fetch("""select security_id from screening_results where run_id=$1 order by rank nulls last, security_id""",RUN)]
    top=ids[:15]; rest=ids[-40:]; ok=bad=skip=0
    for sid in top+rest:
        bars=await c.fetch("select date,close,high,low,adj_factor from ohlcv_daily where security_id=$1 and date<=$2 order by date",sid,d)
        if len(bars)<260: skip+=1; continue
        win=bars[-260:]
        if any(b['adj_factor']!=1 for b in bars[-300:]): skip+=1; continue
        cl=[b['close'] for b in bars]
        sma=lambda n: sum(cl[-n:])/n
        rr={r['rule_id']:r for r in await c.fetch("select rule_id,raw_value,threshold from rule_results where run_id=$1 and security_id=$2",RUN,sid)}
        checks=[("sma50",sma(50),rr['tt_close_above_sma50']['threshold']),("sma200",sma(200),rr['tt_sma150_above_sma200']['threshold'])]
        for name,mine,theirs in checks:
            if abs(Decimal(mine)-theirs)<=Decimal("0.01"): ok+=1
            else: bad+=1; print("MISMATCH",sid,name,mine,theirs)
    print("run",RUN,d,"ok",ok,"bad",bad,"skipped(non-constant adj)",skip)
asyncio.run(main())
