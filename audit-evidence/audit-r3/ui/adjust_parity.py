"""Chart API vs stored rows (read-only). For each symbol, every API daily bar must equal
round(raw * adj_factor, 4) for OHLC, and the traded series must be the raw close.
Prints the volume rule actually observed."""
import json, subprocess, sys, urllib.request
from decimal import Decimal, ROUND_HALF_UP
q = lambda x: x.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
def rows(sym):
    sql = f"select o.date,o.open,o.high,o.low,o.close,o.volume,o.adj_factor,o.adj_close from ohlcv_daily o join securities s on s.id=o.security_id where s.symbol='{sym}' order by 1"
    out = subprocess.run(["docker","exec","momentum25-db-1","psql","-U","momentum25","-d","momentum25","-At","-F","|","-c",sql],capture_output=True,text=True,check=True).stdout.strip().splitlines()
    return {r.split("|")[0]: r.split("|") for r in out}
for sym in sys.argv[1:]:
    db = rows(sym)
    api = json.load(urllib.request.urlopen(f"http://localhost:8000/api/v1/securities/{sym}/ohlcv?interval=1D"))
    bad = vol_adj = vol_raw = 0
    for b in api["bars"]:
        d = db[b["date"]]; f = Decimal(d[6])
        for i, k in ((1,"open"),(2,"high"),(3,"low"),(4,"close")):
            if q(Decimal(d[i]) * f) != Decimal(b[k]):
                bad += 1
                if bad <= 3: print(sym, b["date"], k, "raw", d[i], "factor", d[6], "api", b[k])
        rv = int(d[5])
        if int(b["volume"]) == rv: vol_raw += 1
        if f != 1 and abs(int(b["volume"]) - round(rv / f)) <= 1: vol_adj += 1
    nonunit = sum(1 for r in db.values() if Decimal(r[6]) != 1)
    print(f"{sym}: api bars {len(api['bars'])}, db rows {len(db)}, OHLC mismatches {bad}, non-unit-factor rows {nonunit}, volume==raw {vol_raw}, volume==raw/factor on factored rows {vol_adj}")
