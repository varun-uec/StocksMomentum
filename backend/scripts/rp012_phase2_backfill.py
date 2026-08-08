"""RP-012 Phase 2 — run the real legacy-overlap backfill against the live DB.

Executes :class:`LegacyOverlapBackfill` over the full overlap window
(2019-09-30 → 2024-07-05) using the live ``BhavcopyProvider`` (real NSE legacy
archive) and the production database. Idempotent and resumable — per-day
``ON CONFLICT`` upserts skip already-written days on a re-run.

Usage:  python scripts/rp012_phase2_backfill.py [START_ISO] [END_ISO]
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import date

from momentum25.application.use_cases.research.legacy_overlap_backfill import (
    OVERLAP_END,
    OVERLAP_START,
    LegacyOverlapBackfill,
)
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.repositories.historical_backfill import (
    SqlLegacyOHLCVRepository,
    SqlValidationGapLogRepository,
)
from momentum25.infrastructure.persistence.repositories.security import (
    SqlSecurityRepository,
)
from momentum25.infrastructure.providers.bhavcopy import BhavcopyProvider


async def main(start: date, end: date) -> None:
    """Run the backfill and print a JSON summary."""
    db = get_database()
    async with db.session() as session:
        backfill = LegacyOverlapBackfill(
            provider=BhavcopyProvider(),
            security_repo=SqlSecurityRepository(session),
            legacy_repo=SqlLegacyOHLCVRepository(session),
            gap_log_repo=SqlValidationGapLogRepository(session),
        )
        summary = await backfill.execute(start=start, end=end)
    print(json.dumps(summary.to_report(), indent=2))


if __name__ == "__main__":
    _start = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else OVERLAP_START
    _end = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else OVERLAP_END
    asyncio.run(main(_start, _end))
