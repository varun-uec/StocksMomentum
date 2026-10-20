"""Build the production walk-forward providers from a read-only CSV export.

Mirrors SqlPriceHistoryProvider.load / SqlSurvivorshipEligibilityProvider.load /
SqlBenchmarkProvider.load exactly, but from CSV instead of a live session.
"""
from __future__ import annotations

import csv
import os
import pickle
from datetime import date
from decimal import Decimal

from momentum25.infrastructure.persistence.repositories.walk_forward_market_data import (
    SqlBenchmarkProvider,
    SqlPriceHistoryProvider,
    SqlSurvivorshipEligibilityProvider,
)

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
CACHE = os.path.join(DATA, "bars.pkl")


def d(s: str) -> date | None:
    return date.fromisoformat(s) if s else None


def load_bars(name: str = "ohlcv") -> dict[int, list[tuple]]:
    """security_id -> [(date, open, high, low, close, volume, adj_factor, adj_close, turnover)]."""
    cache = CACHE if name == "ohlcv" else os.path.join(DATA, f"{name}.pkl")
    if os.path.exists(cache):
        with open(cache, "rb") as f:
            return pickle.load(f)
    bars: dict[int, list[tuple]] = {}
    with open(os.path.join(DATA, f"{name}.csv")) as f:
        for r in csv.DictReader(f):
            bars.setdefault(int(r["security_id"]), []).append(
                (
                    d(r["date"]),
                    Decimal(r["open"]),
                    Decimal(r["high"]),
                    Decimal(r["low"]),
                    Decimal(r["close"]),
                    int(r["volume"]) if r["volume"] else None,
                    Decimal(r["adj_factor"]) if r["adj_factor"] else None,
                    Decimal(r["adj_close"]) if r["adj_close"] else None,
                    Decimal(r["turnover_value"]) if r["turnover_value"] else None,
                )
            )
    with open(cache, "wb") as f:
        pickle.dump(bars, f)
    return bars


def securities() -> list[dict]:
    return list(csv.DictReader(open(os.path.join(DATA, "securities.csv"))))


def price_provider(bars, start: date, end: date) -> SqlPriceHistoryProvider:
    """Same rows and arithmetic as SqlPriceHistoryProvider.load."""
    series = {}
    for sid, rows in bars.items():
        for (dt, o, _h, _l, _c, _v, f, ac, _t) in rows:
            if dt < start or dt > end or ac is None:
                continue
            ds, os_, cs = series.setdefault(sid, ([], [], []))
            ds.append(dt)
            os_.append(o * f)
            cs.append(ac)
    return SqlPriceHistoryProvider(series)


def universe_provider(exchanges=("NSE",)) -> SqlSurvivorshipEligibilityProvider:
    """Same filter as SqlSurvivorshipEligibilityProvider.load (exchange == 'NSE')."""
    rows = [
        (int(r["id"]), d(r["listing_date"]), d(r["delisting_date"]))
        for r in securities()
        if r["exchange"] in exchanges and r["listing_date"]
    ]
    return SqlSurvivorshipEligibilityProvider(rows)


def benchmark_provider(start: date, end: date) -> SqlBenchmarkProvider:
    rows = sorted(
        (d(r["date"]), Decimal(r["close"]))
        for r in csv.DictReader(open(os.path.join(DATA, "bench.csv")))
        if start <= d(r["date"]) <= end
    )
    return SqlBenchmarkProvider("NIFTY500", [r[0] for r in rows], [r[1] for r in rows])
