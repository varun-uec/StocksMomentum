"""RP-012 Phase 2 — fill the current-provider (ohlcv_daily) survivorship gap.

Computes the target set dynamically: every currently-inactive plain-equity
security present in ``legacy_ohlcv_daily`` within the overlap window that is
missing *some or all* of that same-window data from ``ohlcv_daily``. This is the
broadened population (RP-012 continuation): the original run covered only the 58
wholly-absent RENAME cases; genuinely-delisted names (no ISIN-sharing successor)
carry the identical gap for the identical reason — production's symbol-keyed
ingestion never fetched history for a ticker absent from today's active universe.

ETFs/funds and the ``SINGLE`` fixture are excluded (separate tickets), matching
the historical-ISIN backfill cohort. Each target is backfilled from the CURRENT
provider (``sec_bhavdata_full`` daily snapshots) via
:class:`CurrentProviderGapBackfill`. Already-present ``ohlcv_daily`` rows are
passed as ``skip_existing`` so partial-gap securities' existing production bars
(and their derived ``adj_close``/``adj_factor``) are never overwritten — only
genuinely missing bars are filled. Provenance stays clean: every written price
originates from the current provider.

Usage:  python scripts/rp012_current_provider_gap_backfill.py [START_ISO] [END_ISO]
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import date

from sqlalchemy import text

from momentum25.application.use_cases.research.current_provider_gap_backfill import (
    CurrentProviderGapBackfill,
)
from momentum25.application.use_cases.research.legacy_overlap_backfill import (
    OVERLAP_END,
    OVERLAP_START,
)
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.repositories.ohlcv import SqlOHLCVRepository
from momentum25.infrastructure.providers.bhavcopy import BhavcopyProvider

# Every currently-inactive plain-equity security (ETFs/funds and the SINGLE
# fixture excluded — separate tickets) with a real, in-window legacy print that
# is missing from ohlcv_daily. Deterministic and idempotent: pinned by ISIN (the
# backfill's lookup key, stable across renames), re-runs upsert-skip written rows.
_TARGETS_SQL = text(
    """
    SELECT s.id, s.isin
    FROM securities s
    WHERE s.is_active IS FALSE
      AND s.isin IS NOT NULL
      AND NOT (s.symbol ILIKE '%ETF%' OR s.name ILIKE '%ETF%')
      AND s.symbol <> 'SINGLE'
      AND EXISTS (
          SELECT 1 FROM legacy_ohlcv_daily l
          WHERE l.security_id = s.id
            AND l.date BETWEEN :start AND :end
            AND NOT EXISTS (
                SELECT 1 FROM ohlcv_daily o
                WHERE o.security_id = s.id AND o.date = l.date))
    ORDER BY s.id
    """
)

# In-window ohlcv_daily dates already held for the target securities — protected
# from being overwritten (partial-gap securities keep their production rows).
_PRESENT_SQL = text(
    """
    SELECT o.security_id, o.date
    FROM ohlcv_daily o
    WHERE o.security_id = ANY(:ids)
      AND o.date BETWEEN :start AND :end
    """
)


async def main(start: date, end: date) -> None:
    """Run the current-provider gap backfill and print a JSON summary."""
    db = get_database()
    async with db.session() as session:
        rows = (await session.execute(_TARGETS_SQL, {"start": start, "end": end})).fetchall()
        targets = {row[0]: row[1] for row in rows}

        present: dict[int, set[date]] = {}
        if targets:
            present_rows = await session.execute(
                _PRESENT_SQL, {"ids": list(targets), "start": start, "end": end}
            )
            for sid, d in present_rows.fetchall():
                present.setdefault(sid, set()).add(d)

        backfill = CurrentProviderGapBackfill(
            provider=BhavcopyProvider(),
            ohlcv_repo=SqlOHLCVRepository(session),
        )
        summary = await backfill.execute(
            targets=targets, start=start, end=end, skip_existing=present
        )
    print(json.dumps(summary.to_report(), indent=2))


if __name__ == "__main__":
    _start = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else OVERLAP_START
    _end = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else OVERLAP_END
    asyncio.run(main(_start, _end))
