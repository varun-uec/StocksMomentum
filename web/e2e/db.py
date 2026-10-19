"""Prepare the synthetic E2E database. Run with the backend venv.

``seed``  Sixteen synthetic symbols, E2E10Y0..15, with 10 years of daily bars.
          NFR-11 times a chart opening 10 years of bars, and the real dataset
          starts in 2019 (about 6.9 years). The M13 benchmark fills a 4 × 4
          layout with them. They exist only in the marked E2E database. Idempotent.
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
import os
import sys
from urllib.parse import unquote, urlsplit

import asyncpg

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
        count = await conn.fetchval(
            "SELECT min(c) FROM (SELECT count(*) c FROM ohlcv_daily o JOIN securities s"
            " ON s.id = o.security_id WHERE s.symbol LIKE 'E2E10Y%' GROUP BY s.id) t"
        )
        print(f"seeded 16 symbols, at least {count} bars each")
    finally:
        await conn.close()


url = os.environ.get("E2E_DATABASE_URL", "")
if not url:
    sys.exit("set E2E_DATABASE_URL to the dedicated E2E database (make e2e-db)")
asyncio.run(main(sys.argv[1], url, *sys.argv[2:]))
