"""RP-012 Phase 3 — legacy-archive backfill of the full pre-overlap range.

Backfills 1994-11-03 → 2019-09-29 (the day before the already-completed Phase 2
overlap window) into ``legacy_ohlcv_daily`` using the exact same
:class:`LegacyOverlapBackfill` resolution / validation-gap pipeline built and
fixed in Phase 2. Only the lower ``floor`` guard is relaxed (to
``LEGACY_INCEPTION``); nothing about resolution, logging, or persistence is
redesigned.

The range is processed in ascending calendar-year chunks. A JSON checkpoint of
the last fully-completed chunk end-date is written after each chunk, so a
session-limit interruption resumes from the next chunk rather than restarting
(per-day ``ON CONFLICT`` upserts already make any partial chunk idempotent).

Usage:  python scripts/rp012_phase3_backfill.py [START_ISO] [END_ISO]
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import date
from pathlib import Path

from momentum25.application.use_cases.research.legacy_overlap_backfill import (
    LEGACY_INCEPTION,
    OVERLAP_START,
    BackfillSummary,
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

# Phase 3 pre-overlap range: inception → day before the overlap window.
PHASE3_START: date = LEGACY_INCEPTION
PHASE3_END: date = date(2019, 9, 29)  # OVERLAP_START - 1 day

_CHECKPOINT = Path(__file__).resolve().parent.parent / "rp012_phase3_checkpoint.json"


def _year_chunks(start: date, end: date) -> list[tuple[date, date]]:
    """Split ``[start, end]`` into non-overlapping calendar-year bands."""
    chunks: list[tuple[date, date]] = []
    year = start.year
    while year <= end.year:
        lo = max(start, date(year, 1, 1))
        hi = min(end, date(year, 12, 31))
        chunks.append((lo, hi))
        year += 1
    return chunks


def _load_checkpoint() -> date | None:
    """Return the last-completed chunk end-date, or ``None`` if no checkpoint."""
    if not _CHECKPOINT.exists():
        return None
    data = json.loads(_CHECKPOINT.read_text())
    value = data.get("last_completed_end")
    return date.fromisoformat(value) if value else None


def _save_checkpoint(last_end: date, totals: dict[str, int]) -> None:
    """Persist the checkpoint marker and running totals atomically."""
    payload = {"last_completed_end": last_end.isoformat(), "totals": totals}
    tmp = _CHECKPOINT.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(_CHECKPOINT)


def _accumulate(totals: dict[str, int], summary: BackfillSummary) -> None:
    """Add a chunk summary's integer counters into the running totals."""
    report = summary.to_report()
    for key, value in report.items():
        if isinstance(value, int):
            totals[key] = totals.get(key, 0) + value


async def main(start: date, end: date) -> None:
    """Run the chunked, checkpointed Phase 3 backfill and print a JSON summary."""
    if start < PHASE3_START:
        raise SystemExit(f"start must be >= {PHASE3_START.isoformat()}")
    if end >= OVERLAP_START:
        raise SystemExit(
            f"end must be < {OVERLAP_START.isoformat()} (overlap window is Phase 2)"
        )

    checkpoint = _load_checkpoint()
    totals: dict[str, int] = {}
    if _CHECKPOINT.exists():
        totals = json.loads(_CHECKPOINT.read_text()).get("totals", {})

    chunks = _year_chunks(start, end)
    db = get_database()

    for lo, hi in chunks:
        if checkpoint is not None and hi <= checkpoint:
            continue  # already completed in a prior session
        async with db.session() as session:
            backfill = LegacyOverlapBackfill(
                provider=BhavcopyProvider(),
                security_repo=SqlSecurityRepository(session),
                legacy_repo=SqlLegacyOHLCVRepository(session),
                gap_log_repo=SqlValidationGapLogRepository(session),
            )
            summary = await backfill.execute(start=lo, end=hi, floor=PHASE3_START)
        _accumulate(totals, summary)
        _save_checkpoint(hi, totals)
        print(json.dumps({"chunk": [lo.isoformat(), hi.isoformat()], **summary.to_report()}))
        sys.stdout.flush()

    print(json.dumps({"phase3_totals": totals}, indent=2))


if __name__ == "__main__":
    _start = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else PHASE3_START
    _end = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else PHASE3_END
    asyncio.run(main(_start, _end))
