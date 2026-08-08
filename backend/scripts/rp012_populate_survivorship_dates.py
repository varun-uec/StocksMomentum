"""RP-012 §3.3 — populate listing_date / last_trade_date / delisting_date.

Deterministic, single-pass population of the three survivorship columns on
``securities`` from observed bar coverage across BOTH ``ohlcv_daily`` and
``legacy_ohlcv_daily`` combined, using the pure
:func:`classify_survivorship` rule (T_gap = 60 consecutive trading days).

Must be run AFTER the current-provider gap backfill lands, since that changes
what "last observed bar" means for the affected securities.

``listing_date`` is (re)set to the earliest observed bar per RP-012 §3.3. This
redefines the field from the prior nsemine instrument-master ``date_of_listing``;
the two are equivalent for the survivorship screening *output* (a security cannot
be screened before its earliest bar regardless), and the earliest-bar definition
is what period-correct-split resolution requires. Preserving the true IPO date in
a separate column is a logged backlog item.

Usage:  python scripts/rp012_populate_survivorship_dates.py [--dry-run]
"""

from __future__ import annotations

import asyncio
import bisect
import sys

from sqlalchemy import text

from momentum25.application.use_cases.research.legacy_overlap_backfill import OVERLAP_END
from momentum25.domain.research.survivorship import classify_survivorship
from momentum25.infrastructure.persistence.database import get_database

_COVERAGE_SQL = text(
    """
    SELECT security_id, MIN(d) AS first_bar, MAX(d) AS last_bar
    FROM (
        SELECT security_id, date AS d FROM ohlcv_daily
        UNION ALL
        SELECT security_id, date AS d FROM legacy_ohlcv_daily
    ) u
    GROUP BY security_id
    """
)

_PANEL_DATES_SQL = text(
    """
    SELECT DISTINCT d FROM (
        SELECT date AS d FROM ohlcv_daily
        UNION
        SELECT date AS d FROM legacy_ohlcv_daily
    ) u
    ORDER BY d
    """
)

_UPDATE_SQL = text(
    """
    UPDATE securities
    SET listing_date = :listing_date,
        last_trade_date = :last_trade_date,
        delisting_date = :delisting_date
    WHERE id = :id
    """
)


async def main(dry_run: bool) -> None:
    """Compute and persist survivorship dates; print a JSON-ish summary."""
    db = get_database()
    async with db.session() as session:
        panel_dates = [row[0] for row in (await session.execute(_PANEL_DATES_SQL)).fetchall()]
        coverage = (await session.execute(_COVERAGE_SQL)).fetchall()

        panel_last = panel_dates[-1] if panel_dates else None
        delisted = 0
        active = 0
        indeterminate_boundary = 0
        updates: list[dict[str, object]] = []
        for security_id, first_bar, last_bar in coverage:
            # Panel trading dates strictly after the last observed bar.
            after = len(panel_dates) - bisect.bisect_right(panel_dates, last_bar)
            cls = classify_survivorship(first_bar, last_bar, after)
            delisting_date = cls.delisting_date
            # Truncation guard: a security whose last observed bar coincides with
            # the Phase-2 overlap-window end has data that was truncated at the
            # backfill boundary, not necessarily a delisting. We cannot
            # distinguish a genuine 2024-07-05 delisting from data-truncation, so
            # we do NOT assert a delisting (leave delisting_date NULL) rather than
            # fabricate one — e.g. ADOR (ex-ADORWELD) still trades in 2026 but its
            # current-symbol ingestion is separately broken, so its data ends here.
            if cls.delisted and last_bar == OVERLAP_END:
                delisting_date = None
                indeterminate_boundary += 1
            elif cls.delisted:
                delisted += 1
            else:
                active += 1
            updates.append(
                {
                    "id": security_id,
                    "listing_date": cls.listing_date,
                    "last_trade_date": cls.last_trade_date,
                    "delisting_date": delisting_date,
                }
            )

        if not dry_run:
            for chunk_start in range(0, len(updates), 500):
                for row in updates[chunk_start : chunk_start + 500]:
                    await session.execute(_UPDATE_SQL, row)
                await session.commit()

        print(
            f"securities_classified={len(updates)} delisted={delisted} active={active} "
            f"indeterminate_boundary={indeterminate_boundary} "
            f"panel_last={panel_last} panel_trading_days={len(panel_dates)} "
            f"dry_run={dry_run}"
        )


if __name__ == "__main__":
    asyncio.run(main(dry_run="--dry-run" in sys.argv[1:]))
