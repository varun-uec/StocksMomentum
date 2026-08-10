"""RP-014 — run the BSE legacy-archive backfill against the live DB.

Executes :class:`BseLegacyBackfill` over the pre-UDiFF range
(2006-03-01 → 2023-12-29, measured in RP-014: BSE's public bhavcopy archive
begins 2006-03-01 and the UDiFF format begins 2024-01-02) using the live
``BSEBhavcopyProvider`` (real BSE EQ_CSV archive) and the production database.
Idempotent and resumable — per-day ``ON CONFLICT`` upserts skip already-written
days on a re-run, and the learned SC_CODE → ISIN junction is insert-only.

Usage:  python scripts/rp014_bse_legacy_backfill.py [START_ISO] [END_ISO]
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import date, timedelta

from momentum25.application.use_cases.research.bse_legacy_backfill import (
    BseLegacyBackfill,
)
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.models import BSELegacyOHLCVDailyModel
from momentum25.infrastructure.persistence.repositories.historical_backfill import (
    SqlBSEScripJunctionRepository,
    SqlLegacyOHLCVRepository,
)
from momentum25.infrastructure.persistence.repositories.security import (
    SqlSecurityRepository,
)
from momentum25.infrastructure.providers.bse_bhavcopy import (
    BSE_LEGACY_START,
    UDIFF_START,
    BSEBhavcopyProvider,
)


async def main(start: date, end: date) -> None:
    """Run the backfill and print a JSON summary."""
    db = get_database()
    async with db.session() as session:
        backfill = BseLegacyBackfill(
            provider=BSEBhavcopyProvider(),
            security_repo=SqlSecurityRepository(session),
            bse_repo=SqlLegacyOHLCVRepository(session, model_cls=BSELegacyOHLCVDailyModel),
            junction_repo=SqlBSEScripJunctionRepository(session),
        )
        summary = await backfill.execute(start=start, end=end)
    print(json.dumps(summary.to_report(), indent=2))


if __name__ == "__main__":
    _start = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else BSE_LEGACY_START
    _end = (
        date.fromisoformat(sys.argv[2])
        if len(sys.argv) > 2
        else UDIFF_START - timedelta(days=1)
    )
    asyncio.run(main(_start, _end))