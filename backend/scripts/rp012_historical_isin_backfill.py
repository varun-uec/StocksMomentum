"""RP-012 — populate ``securities.isin`` for historical/inactive ghost rows.

Selects every ``is_active=false, isin IS NULL`` security that is a plain equity
(ETFs/funds and the ``SINGLE`` fixture are excluded — they are tracked
separately) and recovers its ISIN off the legacy NSE archive via
:class:`HistoricalIsinBackfill`. Candidate probe dates are, in order,
``last_trade_date`` (a guaranteed real trading day for the ghost's own ticker),
``listing_date``, and the interval midpoint — so a single deterministic archive
read per date resolves the period-correct ISIN without fabricating anything.

Usage:  python scripts/rp012_historical_isin_backfill.py
"""

from __future__ import annotations

import asyncio
import json
from datetime import date

from sqlalchemy import text

from momentum25.application.use_cases.research.historical_isin_backfill import (
    HistoricalIsinBackfill,
    IsinProbeTarget,
)
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.repositories.security import SqlSecurityRepository
from momentum25.infrastructure.providers.bhavcopy import BhavcopyProvider

# The historical-ghost cohort: inactive rows whose ISIN was never captured,
# excluding ETFs/funds and the SINGLE fixture (both tracked as separate tickets).
_COHORT_SQL = text(
    """
    SELECT id, symbol, listing_date, delisting_date, last_trade_date
    FROM securities
    WHERE is_active = false
      AND isin IS NULL
      AND NOT (symbol ILIKE '%ETF%' OR name ILIKE '%ETF%')
      AND symbol <> 'SINGLE'
    ORDER BY id
    """
)


def _candidate_dates(
    listing: date | None, delisting: date | None, last_trade: date | None
) -> tuple[date, ...]:
    """Ordered, de-duplicated probe dates inside the ghost's trading interval."""
    ordered: list[date] = []
    for candidate in (last_trade, delisting, listing):
        if candidate is not None and candidate not in ordered:
            ordered.append(candidate)
    if listing is not None and delisting is not None and delisting > listing:
        midpoint = listing + (delisting - listing) / 2
        if midpoint not in ordered:
            ordered.append(midpoint)
    return tuple(ordered)


async def main() -> None:
    """Run the historical-ISIN backfill and print a JSON summary."""
    db = get_database()
    async with db.session() as session:
        rows = (await session.execute(_COHORT_SQL)).fetchall()
        targets = [
            IsinProbeTarget(
                security_id=row[0],
                symbol=row[1],
                candidate_dates=_candidate_dates(row[2], row[3], row[4]),
            )
            for row in rows
        ]
        backfill = HistoricalIsinBackfill(
            provider=BhavcopyProvider(),
            security_repo=SqlSecurityRepository(session),
        )
        summary = await backfill.execute(targets)
        await session.commit()
    print(json.dumps(summary.to_report(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
