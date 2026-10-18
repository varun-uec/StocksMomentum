"""Prepare the E2E database clone. Run with the backend venv.

``seed``  Ten synthetic symbols, E2E10Y0..9, with 10 years of daily bars. NFR-11
          times a chart opening 10 years of bars, and the real dataset starts in
          2019 (about 6.9 years). They exist only in the clone. Idempotent.
``reset`` Delete every saved workspace and drawing, so each test starts clean.

The database URL comes from ``M25_DATABASE_URL`` or ``E2E_DATABASE_URL``.
"""

import asyncio
import os
import sys

import asyncpg

SQL = """
INSERT INTO securities (symbol, name, exchange, is_active)
SELECT 'E2E10Y' || n, 'Synthetic 10-year series ' || n, 'NSE', true
FROM generate_series(0, 9) AS n
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
        print(f"seeded 10 symbols, at least {count} bars each")
    finally:
        await conn.close()


url = os.environ.get("M25_DATABASE_URL") or os.environ["E2E_DATABASE_URL"]
asyncio.run(main(sys.argv[1], url))
