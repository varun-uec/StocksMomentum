"""Prepare the synthetic E2E database. Run with the backend venv.

``seed``  Sixteen synthetic symbols, E2E10Y0..15, with 10 years of daily bars.
          NFR-11 times a chart opening 10 years of bars, and the real dataset
          starts in 2019 (about 6.9 years). The M13 benchmark fills a 4 × 4
          layout with them. They exist only in the marked E2E database. Also the
          chart fixture E2ECANDLE (see ``chart_fixture_bars``). Idempotent.
``reset`` Delete every saved workspace, drawing and alert, so each test starts clean.
``age-alerts`` Move every alert's ``armed_after`` 30 days back, so an E2E test can
          watch one fire on bars already stored (the synthetic fixture gets no new bars).
``holdout-provenance`` Set the isolated 2023–2025 E2E hold-out months to published or
          reconstructed, for the Strategy Studio insufficient-provenance case.
``bump-synthetic-close`` Correct the latest synthetic E2E10Y0 bar by 0.0001 for
          each invocation, forcing a new manifest and screening execution.

The database URL comes from ``E2E_DATABASE_URL`` only. Every command verifies the
database name returned by PostgreSQL before it can read or mutate anything.
Destructive test data lives in a separately provisioned ``*_e2e`` database.
"""

import asyncio
import math
import os
import random
import sys
from datetime import date, timedelta
from decimal import Decimal
from urllib.parse import unquote, urlsplit

import asyncpg

# A chart-only fixture. Its 1:2 split leaves factor 0.5 on every earlier bar.
CHART_FIXTURE = "E2ECANDLE"
CHART_FIXTURE_SPLIT = date(2026, 6, 22)


def chart_fixture_bars() -> list[tuple[date, int, int, int, int, int]]:
    """Return E2ECANDLE's adjusted daily bars as (date, open, high, low, close, volume).

    Prices are counts of the 0.05 tick. The bars vary like a traded stock:
    volatility changes every 60 sessions, some sessions gap, and about one bar
    in five is a doji, hammer, shooting star or strong-bodied bar. The other
    fixtures' high and low sit at a fixed 1% around the open, so their wicks all
    look alike; screening goldens depend on them, so they stay as they are.
    ``random.Random.random`` is the one generator Python keeps stable across
    versions, and only plain arithmetic follows it, so the bars are deterministic.
    """
    rng = random.Random(20261020)

    def shock() -> float:
        return (rng.random() + rng.random() + rng.random() - 1.5) * 2  # about N(0, 1)

    close_ticks, bars, day, i = 16_000, [], date(2024, 8, 5), 0
    while day <= date(2026, 8, 7):
        if day.weekday() < 5:
            sigma = (0.008, 0.016, 0.026, 0.012)[(i // 60) % 4]
            drift = (0.0010, -0.0006, 0.0012, 0.0002)[(i // 45) % 4]
            o = close_ticks / 20 * (1 + shock() * sigma * (1.6 if rng.random() < 0.07 else 0.12))
            kind = rng.random()
            if kind < 0.05:  # doji
                body = shock() * sigma * 0.03
                upper, lower = (0.3 + rng.random()) * sigma, (0.3 + rng.random()) * sigma
            elif kind < 0.09:  # hammer
                body = abs(shock()) * sigma * 0.25
                upper, lower = rng.random() * sigma * 0.1, (1.2 + rng.random()) * sigma
            elif kind < 0.13:  # shooting star
                body = -abs(shock()) * sigma * 0.25
                upper, lower = (1.2 + rng.random()) * sigma, rng.random() * sigma * 0.1
            elif kind < 0.18:  # strong body
                body = (1 if rng.random() < 0.5 else -1) * (1.6 + rng.random()) * sigma
                upper, lower = rng.random() * sigma * 0.08, rng.random() * sigma * 0.08
            else:
                body = drift + shock() * sigma
                upper, lower = abs(shock()) * sigma * 0.45, abs(shock()) * sigma * 0.45
            c = o * (1 + body)
            open_ticks, close_ticks = round(o * 20), round(c * 20)
            high_ticks = max(math.ceil(max(o, c) * (1 + upper) * 20), open_ticks, close_ticks)
            low_ticks = min(math.floor(min(o, c) * (1 - lower) * 20), open_ticks, close_ticks)
            activity = (sigma / 0.008) ** 0.5 * (1.8 if kind < 0.18 else 1)
            volume = 2 * round(200_000 * activity * (0.6 + 0.8 * rng.random()))
            bars.append((day, open_ticks, high_ticks, low_ticks, close_ticks, volume))
            i += 1
        day += timedelta(days=1)
    return bars


def chart_fixture_rows(security_id: int) -> list[tuple[object, ...]]:
    """Return E2ECANDLE's stored rows: raw prints, so bars before the split trade at double."""
    rows: list[tuple[object, ...]] = []
    for day, *ticks, volume in chart_fixture_bars():
        factor = Decimal("0.5") if day < CHART_FIXTURE_SPLIT else Decimal(1)
        o, h, low, c = (Decimal(t) / 20 / factor for t in ticks)
        raw_volume = int(volume * factor)
        rows.append((security_id, day, o, h, low, c, raw_volume, c * raw_volume, factor))
    return rows

SQL = """
INSERT INTO securities (symbol, name, exchange, is_active)
SELECT 'E2E10Y' || n, 'Synthetic 10-year series ' || n, 'NSE', true
FROM generate_series(0, 15) AS n
ON CONFLICT (symbol) DO NOTHING;

INSERT INTO securities (symbol, name, exchange, is_active)
VALUES
    ('RELIANCE', 'Synthetic E2E fixture RELIANCE', 'NSE', true),
    ('TCS', 'Synthetic E2E fixture TCS', 'NSE', true),
    ('INFY', 'Synthetic E2E fixture INFY', 'NSE', true),
    ('ITC', 'Synthetic E2E fixture ITC', 'NSE', true),
    ('HDFCBANK', 'Synthetic E2E fixture HDFCBANK', 'NSE', true),
    ('GOLDIAM', 'Synthetic E2E fixture GOLDIAM', 'NSE', true)
ON CONFLICT (symbol) DO UPDATE
SET name = EXCLUDED.name, exchange = EXCLUDED.exchange, is_active = true;

INSERT INTO ohlcv_daily (
    security_id, date, open, high, low, close, volume, turnover_value, adj_factor
)
SELECT s.id, d::date,
       raw_price, raw_price * 1.01, raw_price * 0.99,
       CASE WHEN s.symbol = 'GOLDIAM' THEN raw_price ELSE raw_price * (1 + 0.002 * sin(i)) END,
       1000000 + (i % 7) * 1000,
       CASE WHEN s.symbol = 'GOLDIAM' THEN raw_price ELSE raw_price * (1 + 0.002 * sin(i)) END
           * (1000000 + (i % 7) * 1000),
       CASE
           WHEN s.symbol <> 'GOLDIAM' THEN 1
           WHEN d::date < DATE '2022-03-28' THEN 0.15
           WHEN d::date < DATE '2026-07-10' THEN 0.75
           ELSE 1
       END
FROM securities s
CROSS JOIN LATERAL (
    SELECT d, row_number() OVER (ORDER BY d) AS i
    FROM generate_series(DATE '2016-08-08', DATE '2026-08-07', INTERVAL '1 day') AS d
    WHERE extract(isodow FROM d) < 6
) days
CROSS JOIN LATERAL (
    SELECT
        CASE
            WHEN s.symbol LIKE 'E2E10Y%'
                THEN 0.00035 + substring(s.symbol FROM 7)::integer * 0.0001
            ELSE 0.0004
        END AS growth,
        CASE
            WHEN s.symbol = 'GOLDIAM' THEN 100
            ELSE 100 * exp(i * CASE
                WHEN s.symbol LIKE 'E2E10Y%'
                    THEN 0.00035 + substring(s.symbol FROM 7)::integer * 0.0001
                ELSE 0.0004
            END) * (1 + 0.005 * sin(i / 17.0))
        END AS base_price,
        CASE
            WHEN s.symbol = 'GOLDIAM' AND d::date < DATE '2022-03-28' THEN 5
            WHEN s.symbol = 'GOLDIAM' AND d::date >= DATE '2026-07-10' THEN 0.75
            ELSE 1
        END AS split_multiplier
) parameters
CROSS JOIN LATERAL (SELECT base_price * split_multiplier AS raw_price) prices
WHERE s.symbol LIKE 'E2E10Y%'
   OR s.symbol IN ('RELIANCE', 'TCS', 'INFY', 'ITC', 'HDFCBANK', 'GOLDIAM')
ON CONFLICT (security_id, date) DO UPDATE SET
    open = EXCLUDED.open,
    high = EXCLUDED.high,
    low = EXCLUDED.low,
    close = EXCLUDED.close,
    volume = EXCLUDED.volume,
    turnover_value = EXCLUDED.turnover_value,
    adj_factor = EXCLUDED.adj_factor;

INSERT INTO benchmark_index_daily (index_code, date, close)
SELECT 'NIFTY500', d::date, 10000 * exp(i * 0.00025)
FROM (
    SELECT d::date AS d, row_number() OVER (ORDER BY d) AS i
    FROM generate_series(DATE '2016-08-08', DATE '2026-08-07', INTERVAL '1 day') AS d
    WHERE extract(isodow FROM d) < 6
) days
ON CONFLICT (index_code, date) DO UPDATE SET close = EXCLUDED.close;
"""


def database_name(url: str) -> str:
    """Return the configured E2E database name or fail before connecting."""
    parsed = urlsplit(url.replace("postgresql+asyncpg://", "postgresql://"))
    name = unquote(parsed.path.lstrip("/"))
    if parsed.scheme not in {"postgres", "postgresql"} or not name.endswith("_e2e"):
        sys.exit(
            "refusing database operation: E2E_DATABASE_URL must name a PostgreSQL database "
            "ending in _e2e"
        )
    return name


async def main(command: str, url: str, *arguments: str) -> None:
    """Verify and operate on a database dedicated to synthetic E2E fixtures."""
    if command not in {
        "verify",
        "seed",
        "reset",
        "age-alerts",
        "holdout-provenance",
        "bump-synthetic-close",
        "extra-bar",
        "drop-extra-bar",
    }:
        sys.exit("usage: db.py {verify|seed|reset|age-alerts|holdout-provenance}")
    if command == "holdout-provenance":
        if len(arguments) != 1 or arguments[0] not in {"published", "reconstructed"}:
            sys.exit("usage: db.py holdout-provenance {published|reconstructed}")
    expected_database = database_name(url)
    conn = await asyncpg.connect(url.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        actual_database = await conn.fetchval("SELECT current_database()")
        if actual_database != expected_database:
            sys.exit(
                "refusing database operation: the connected database name does not match "
                "E2E_DATABASE_URL"
            )
        if command == "verify":
            marker_exists = await conn.fetchval(
                "SELECT to_regclass('public.wickstreet_e2e_guard') IS NOT NULL"
            )
            if not marker_exists:
                table_count = await conn.fetchval(
                    "SELECT count(*) FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
                )
                if table_count:
                    sys.exit(
                        "refusing database operation: an existing database must carry the "
                        "synthetic E2E marker"
                    )
                await conn.execute(
                    "CREATE TABLE wickstreet_e2e_guard "
                    "(singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton), "
                    "database_name text NOT NULL)"
                )
                await conn.execute(
                    "INSERT INTO wickstreet_e2e_guard (singleton, database_name) VALUES (true, $1)",
                    actual_database,
                )
            else:
                marked_database = await conn.fetchval(
                    "SELECT database_name FROM wickstreet_e2e_guard WHERE singleton = true"
                )
                if marked_database != actual_database:
                    sys.exit(
                        "refusing database operation: the synthetic E2E marker does not "
                        "match this database"
                    )
            print(f"verified isolated synthetic E2E database: {actual_database}")
            return
        marker_exists = await conn.fetchval(
            "SELECT to_regclass('public.wickstreet_e2e_guard') IS NOT NULL"
        )
        if not marker_exists:
            sys.exit(
                "refusing database operation: run the E2E database verification before "
                "using fixtures"
            )
        marked_database = await conn.fetchval(
            "SELECT database_name FROM wickstreet_e2e_guard WHERE singleton = true"
        )
        if marked_database != actual_database:
            sys.exit(
                "refusing database operation: the synthetic E2E marker does not match "
                "this database"
            )
        if command == "reset":
            await conn.execute("DELETE FROM user_documents")
            await conn.execute("DELETE FROM alerts")
            return
        if command == "age-alerts":
            await conn.execute("UPDATE alerts SET armed_after = armed_after - 30")
            return
        if command == "bump-synthetic-close":
            result = await conn.execute(
                "UPDATE ohlcv_daily SET close = close + 0.0001, "
                "turnover_value = (close + 0.0001) * volume "
                "WHERE security_id = (SELECT id FROM securities WHERE symbol = 'E2E10Y0') "
                "AND date = (SELECT max(o.date) FROM ohlcv_daily o "
                "JOIN securities s ON s.id = o.security_id WHERE s.symbol = 'E2E10Y0')"
            )
            if result != "UPDATE 1":
                sys.exit("refusing to correct a missing synthetic E2E10Y0 bar")
            print("corrected one synthetic E2E10Y0 bar")
            return
        if command in {"extra-bar", "drop-extra-bar"}:
            # Journey 5: one TCS bar after the screening run's as-of date, then its removal.
            symbol_id = "(SELECT id FROM securities WHERE symbol = 'TCS')"
            others_max = (
                "(SELECT max(o.date) FROM ohlcv_daily o JOIN securities s ON s.id = o.security_id "
                "WHERE s.symbol <> 'TCS')"
            )
            if command == "drop-extra-bar":
                result = await conn.execute(
                    f"DELETE FROM ohlcv_daily WHERE security_id = {symbol_id} AND date > {others_max}"
                )
                print(f"removed the extra synthetic TCS bar: {result}")
                return
            columns = [
                r["column_name"]
                for r in await conn.fetch(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'ohlcv_daily' "
                    "AND coalesce(column_default, '') NOT LIKE 'nextval%' ORDER BY ordinal_position"
                )
            ]
            values = ["date + 1" if c == "date" else c for c in columns]
            result = await conn.execute(
                f"INSERT INTO ohlcv_daily ({', '.join(columns)}) SELECT {', '.join(values)} "
                f"FROM ohlcv_daily WHERE security_id = {symbol_id} AND date = {others_max}"
            )
            if result != "INSERT 0 1":
                sys.exit("refusing: the synthetic TCS bar to copy is missing")
            print("added one synthetic TCS bar after the run date")
            return
        if command == "holdout-provenance":
            updated = await conn.execute(
                "UPDATE ohlcv_daily SET provenance = $1::varchar, volume = CASE "
                "WHEN $1::varchar = 'reconstructed' AND volume % 1000 = 0 THEN volume + 1 "
                "WHEN $1::varchar = 'published' AND volume % 1000 = 1 THEN volume - 1 "
                "ELSE volume END "
                "WHERE date >= DATE '2023-01-01' AND date <= DATE '2025-12-31' "
                "AND security_id IN (SELECT id FROM securities WHERE symbol LIKE 'E2E10Y%')",
                arguments[0],
            )
            print(f"updated isolated E2E hold-out provenance: {updated}")
            return
        await conn.execute(SQL)
        # Inactive, with a fund-unit ISIN: live screening, market breadth and
        # point-in-time research all skip it, so no screening golden changes.
        security_id = await conn.fetchval(
            "INSERT INTO securities (symbol, name, exchange, isin, is_active) "
            "VALUES ($1, 'Synthetic E2E chart fixture', 'NSE', 'INFE2ECANDL1', false) "
            "ON CONFLICT (symbol) DO UPDATE SET name = EXCLUDED.name, "
            "exchange = EXCLUDED.exchange, isin = EXCLUDED.isin, is_active = false RETURNING id",
            CHART_FIXTURE,
        )
        await conn.executemany(
            "INSERT INTO ohlcv_daily (security_id, date, open, high, low, close, volume, "
            "turnover_value, adj_factor) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) "
            "ON CONFLICT (security_id, date) DO UPDATE SET open = EXCLUDED.open, "
            "high = EXCLUDED.high, low = EXCLUDED.low, close = EXCLUDED.close, "
            "volume = EXCLUDED.volume, turnover_value = EXCLUDED.turnover_value, "
            "adj_factor = EXCLUDED.adj_factor",
            chart_fixture_rows(security_id),
        )
        count = await conn.fetchval(
            "SELECT min(c) FROM (SELECT count(*) c FROM ohlcv_daily o JOIN securities s"
            " ON s.id = o.security_id WHERE s.symbol LIKE 'E2E10Y%' GROUP BY s.id) t"
        )
        print(f"seeded 16 symbols, at least {count} bars each")
    finally:
        await conn.close()


url = os.environ.get("E2E_DATABASE_URL", "")
if __name__ == "__main__":
    if not url:
        sys.exit("set E2E_DATABASE_URL to the dedicated E2E database (make e2e-db)")
    asyncio.run(main(sys.argv[1], url, *sys.argv[2:]))
