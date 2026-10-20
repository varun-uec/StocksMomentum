"""Production runner (method v2) on the read-only export vs the Stage A simulator."""
import csv
from datetime import date, timedelta
from decimal import Decimal
import load, sim, sim2, stageA
from momentum25.application.use_cases.walk_forward import WalkForwardRunner, _months_before
from momentum25.domain.backtest.execution import ExecutionBar
from momentum25.infrastructure.persistence.repositories.walk_forward_market_data import (
    SqlPriceHistoryProvider, SqlSurvivorshipEligibilityProvider, _Series)
from momentum25.infrastructure.calendar.nse_calendar import get_nse_trading_calendar
full = load.load_bars("ohlcv_full")
cal = get_nse_trading_calendar()
for S, E in [(date(2025, 1, 1), date(2026, 7, 31)), (date(2021, 1, 1), date(2026, 7, 31))]:
    lo = S - timedelta(days=400)
    series = {}
    for sid, rows in full.items():
        for (d, o, h, l, c, v, f, ac, tv) in rows:
            if lo <= d <= E:
                series.setdefault(sid, _Series()).append(ExecutionBar(d, o * f, h * f, l * f, c * f, int(v or 0), tv or Decimal(0)))
    rows = [(int(r["id"]), r["exchange"], r["isin"] or None, load.d(r["listing_date"]), load.d(r["delisting_date"]))
            for r in sorted(load.securities(), key=lambda r: int(r["id"])) if r["listing_date"]]
    prod = WalkForwardRunner(cal, SqlPriceHistoryProvider(series), SqlSurvivorshipEligibilityProvider(rows)).run(S, E, Decimal(1_000_000))
    px = sim2.Px(full, lo, E, "computed"); stageA.PX = px
    ses = cal.sessions_between(sim.months_before(S, 13), E)
    ref = sim2.run(px, stageA.universe(("NSE", "BOTH"), True), ses, S, E, Decimal(1_000_000), buy_window=4, cap=Decimal("0.10"))
    pf = [(t.security_id, t.side, t.fill_date, t.fill_price, abs(t.quantity), t.notional) for t in prod.trades]
    rf = [(f.sid, f.side, f.fill_date, f.price, f.qty, f.notional) for f in ref.fills]
    keys_equal = [p[:4] for p in pf] == [r[:4] for r in rf]; maxdiff = max(abs(p[5] - r[5]) for p, r in zip(pf, rf)); print("same (sid, side, date, price):", keys_equal, "max notional diff", maxdiff)
    print(S, E, "fills", len(pf), len(rf), "identical:", pf == rf, "NAV", prod.final_nav, ref.final_nav,
          "return", round(float(prod.total_return), 4), "lower bound", round(float(prod.lower_bound_nav / Decimal(1_000_000) - 1), 4),
          "nontrading", len(prod.nontrading_holdings), "stale fills:", sum(1 for t in prod.trades if series[t.security_id].on(t.fill_date) is None))
