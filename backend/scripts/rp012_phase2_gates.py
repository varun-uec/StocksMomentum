"""RP-012 Phase 2 — run Gate 4a and Gate 4d against the live DB.

Assumes the legacy overlap backfill has already populated ``legacy_ohlcv_daily``.
Runs, in order:

* **Gate 4a** — overlap reconciliation (legacy vs current provider) over the
  whole window; prints real match rates and explained mismatch classes. Canary:
  if it fails, the report says so.
* **Reconstruction** — populates the immutable ``historical_universe`` from the
  liquidity floor.
* **Gate 4d** — universe calibration vs the production eligible universe on a
  sample of matched dates, plus a point-in-time integrity check on 10 random
  dates.

Every number printed is computed from real data; nothing is assumed.
"""

from __future__ import annotations

import asyncio
import json
import random
from datetime import date

from sqlalchemy import text

from momentum25.application.use_cases.research.historical_universe_reconstruction import (
    HistoricalUniverseReconstruction,
)
from momentum25.application.use_cases.research.overlap_reconciliation_report import (
    OverlapReconciliationReport,
)
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.repositories.historical_backfill import (
    SqlHistoricalUniverseRepository,
    SqlLegacyOHLCVRepository,
)
from momentum25.infrastructure.persistence.repositories.ohlcv import SqlOHLCVRepository

# Sample matched dates for Gate 4d calibration — spread across the valid
# reconstruction range (>=252 legacy sessions after 2019-09-30, i.e. ~Oct 2020+),
# each an actual production run_date carrying an eligible universe.
_CALIBRATION_SAMPLE = [
    date(2021, 1, 8),
    date(2021, 4, 13),
    date(2021, 7, 14),
    date(2021, 10, 14),
    date(2022, 1, 17),
    date(2022, 4, 21),
    date(2022, 7, 20),
    date(2022, 10, 24),
    date(2023, 1, 23),
    date(2023, 4, 28),
]


# Production's own liquidity proxy gate (volume_accumulation.py:132): a name is
# only liquid if its estimated daily turnover ``avg_volume50 * latest_close`` is
# at least ``min_turnover_inr`` (INR 1cr for strategy_id=30, identical to the
# reconstruction floor ``L``). Gate 4d compares the production eligible set (P)
# against the L-based reconstruction (R); without applying P's *own* liquidity
# proxy first, P carries names production would itself reject on liquidity,
# inflating the apparent P-vs-R disagreement. The proxy is computed here from
# the live ``ohlcv_daily`` (production's own source) strictly as of ``d``.
_PROD_LIQUIDITY_PROXY_INR = 10_000_000

_PRODUCTION_UNIVERSE_SQL = text(
    """
    WITH elig AS (
        SELECT DISTINCT um.security_id AS sid
        FROM universe_membership um
        JOIN screening_runs r ON r.id = um.run_id
        WHERE r.run_date = :d AND um.eligible IS TRUE
    ),
    ranked AS (
        SELECT o.security_id AS sid, o.volume, o.close,
               row_number() OVER (
                   PARTITION BY o.security_id ORDER BY o.date DESC
               ) AS rn
        FROM ohlcv_daily o
        WHERE o.date <= :d
          AND o.security_id IN (SELECT sid FROM elig)
    ),
    proxy AS (
        SELECT sid,
               avg(volume) FILTER (WHERE rn <= 50) AS avg_volume50,
               max(close) FILTER (WHERE rn = 1) AS latest_close
        FROM ranked
        GROUP BY sid
    )
    SELECT e.sid
    FROM elig e
    JOIN proxy p ON p.sid = e.sid
    WHERE p.avg_volume50 IS NOT NULL
      AND p.latest_close IS NOT NULL
      AND p.avg_volume50 * p.latest_close >= :floor
    """
)


async def _production_universe(session: object, sample: list[date]) -> dict[date, set[int]]:
    """Load the production ELIGIBLE universe (security_ids) for each sample date.

    Applies production's own liquidity proxy gate (``avg_volume50 *
    latest_close >= min_turnover_inr``) to the eligible set before it is handed
    to Gate 4d, so P and R are compared on a like-for-like liquidity basis.
    """
    out: dict[date, set[int]] = {}
    for d in sample:
        result = await session.execute(  # type: ignore[attr-defined]
            _PRODUCTION_UNIVERSE_SQL,
            {"d": d, "floor": _PROD_LIQUIDITY_PROXY_INR},
        )
        out[d] = {row[0] for row in result.fetchall()}
    return out


async def main() -> None:
    """Run Gate 4a, reconstruction, and Gate 4d; print a JSON report."""
    db = get_database()
    report: dict[str, object] = {}

    async with db.session() as session:
        legacy_repo = SqlLegacyOHLCVRepository(session)
        ohlcv_repo = SqlOHLCVRepository(session)
        report["gate_4a"] = await OverlapReconciliationReport(legacy_repo, ohlcv_repo).execute()

    async with db.session() as session:
        legacy_repo = SqlLegacyOHLCVRepository(session)
        universe_repo = SqlHistoricalUniverseRepository(session)
        recon = HistoricalUniverseReconstruction(legacy_repo, universe_repo)
        report["reconstruction"] = await recon.execute()

        production = await _production_universe(session, _CALIBRATION_SAMPLE)
        report["gate_4d_calibration"] = await recon.calibrate(production)

        # Point-in-time integrity on 10 random legacy dates (deterministic seed).
        all_dates = await legacy_repo.distinct_dates(date(2019, 9, 30), date(2024, 7, 5))
        rng = random.Random(42)
        pit_dates = sorted(rng.sample(all_dates, min(10, len(all_dates))))
        report["gate_4d_point_in_time"] = [
            await recon.verify_point_in_time(d) for d in pit_dates
        ]

    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
