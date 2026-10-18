"""Prepare the E2E database clone. Run with the backend venv.

``seed``  Sixteen synthetic symbols, E2E10Y0..15, with 10 years of daily bars.
          NFR-11 times a chart opening 10 years of bars, and the real dataset
          starts in 2019 (about 6.9 years). The M13 benchmark fills a 4 × 4
          layout with them. They exist only in the clone. Idempotent.
``reset`` Delete every saved workspace and drawing, so each test starts clean.

The database URL comes from ``E2E_DATABASE_URL`` only, never ``M25_DATABASE_URL``.
Both commands refuse any database whose name does not end in ``_e2e``: a reset
deletes every saved document, so it must never reach the owner's database.
"""

import asyncio
import os
import sys

import asyncpg

SQL = """
INSERT INTO securities (symbol, name, exchange, is_active)
SELECT 'E2E10Y' || n, 'Synthetic 10-year series ' || n, 'NSE', true
FROM generate_series(0, 15) AS n
ON CONFLICT (symbol) DO NOTHING;

DELETE FROM ohlcv_daily
WHERE security_id IN (SELECT id FROM securities WHERE symbol LIKE 'E2E10Y%');

INSERT INTO ohlcv_daily (security_id, date, open, high, low, close, volume, adj_factor)
SELECT s.id, d::date,
       p, p * 1.01, p * 0.99, p * (1 + 0.004 * sin(i)), 100000 + (i % 7) * 1000, 1
FROM securities s
CROSS JOIN LATERAL (
    SELECT d, row_number() OVER (ORDER BY d) AS i
    FROM generate_series(DATE '2016-08-08', DATE '2026-08-07', INTERVAL '1 day') AS d
    WHERE extract(isodow FROM d) < 6
) days
CROSS JOIN LATERAL (SELECT 100 + 50 * sin(i / 90.0) + i * 0.02 AS p) price
WHERE s.symbol LIKE 'E2E10Y%';
"""


async def main(command: str, url: str) -> None:
    conn = await asyncpg.connect(url.replace("postgresql+asyncpg://", "postgresql://"))
    try:
        if command == "reset":
            await conn.execute("DELETE FROM user_documents")
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
    sys.exit("set E2E_DATABASE_URL to the E2E clone (make e2e-db)")
if not url.rsplit("/", 1)[-1].split("?")[0].endswith("_e2e"):
    sys.exit(f"refusing to touch {url.rsplit('/', 1)[-1]}: not an E2E clone (name must end in _e2e)")
asyncio.run(main(sys.argv[1], url))
