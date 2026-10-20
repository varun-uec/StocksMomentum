"""Reproduce the audit's walk-forward run with the production runner, then
classify every fill as fresh (bar on fill date) or stale (last earlier bar)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import date, timedelta
from decimal import Decimal

from momentum25.application.dto.walk_forward import to_backtest_response
from momentum25.application.use_cases.walk_forward import WalkForwardRunner
from momentum25.infrastructure.calendar.nse_calendar import get_nse_trading_calendar
from momentum25.infrastructure.persistence.repositories.walk_forward_market_data import (
    SURVIVORSHIP_ELIGIBILITY_WARNING,
)

import load

START, END, CAP = date(2025, 1, 1), date(2026, 7, 31), Decimal("1000000")


def main() -> None:
    bars = load.load_bars()
    prices = load.price_provider(bars, START - timedelta(days=400), END)
    runner = WalkForwardRunner(
        calendar=get_nse_trading_calendar(),
        prices=prices,
        universe=load.universe_provider(),
        benchmark=load.benchmark_provider(START, END),
    )
    result = runner.run(START, END, CAP)
    body = to_backtest_response(result, START, END, SURVIVORSHIP_ELIGIBILITY_WARNING)
    raw = body.model_dump_json().encode()
    out = sys.argv[1] if len(sys.argv) > 1 else "wf_repro.json"
    open(out, "wb").write(raw)
    print("sha256", hashlib.sha256(raw).hexdigest())
    print("final_nav", result.final_nav, "total_return", result.total_return)

    dates = {sid: s[0] for sid, s in prices._series.items()}
    stale = [t for t in result.trades if t.fill_date not in set(dates.get(t.security_id, []))]
    tot = sum(abs(t.notional) for t in result.trades)
    st = sum(abs(t.notional) for t in stale)
    print(f"trades {len(result.trades)} stale {len(stale)} stale_notional {st} total_notional {tot} pct {st / tot:.4%}")


if __name__ == "__main__":
    main()
