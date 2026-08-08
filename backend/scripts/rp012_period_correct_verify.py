"""RP-012 — exercise period-correct-split resolution over the real rename chains.

Now that ``securities.isin`` is populated for the historical ghosts, ISIN-keyed
rename chains (>=2 rows sharing one ISIN) exist in the master. This script builds
``intervals_by_symbol`` from every chain member's ``[listing_date, delisting_date]``
interval and confirms that :func:`resolve_period_correct` attributes a bar printed
under a period-correct ticker on a session date to the security that actually held
that ticker on that date — i.e. a 2020 ADANIGAS print resolves to the OLD id
(2605), never to the current ATGL id (469).

Usage:  python scripts/rp012_period_correct_verify.py
"""

from __future__ import annotations

import asyncio
import json
from datetime import date

from sqlalchemy import text

from momentum25.domain.research.period_correct_resolution import (
    PeriodResolutionOutcome,
    SymbolInterval,
    resolve_period_correct,
)
from momentum25.infrastructure.persistence.database import get_database

_CHAINS_SQL = text(
    """
    SELECT s.isin, s.symbol, s.id, s.listing_date, s.delisting_date
    FROM securities s
    JOIN (
        SELECT isin FROM securities
        WHERE isin IS NOT NULL GROUP BY isin HAVING count(*) > 1
    ) c ON c.isin = s.isin
    ORDER BY s.isin, s.listing_date
    """
)

# Deterministic verification probes: (session ticker, session date, expected id).
# Each is a pre-rename bar that must attach to the OLD security, not its successor.
_PROBES: tuple[tuple[str, date, int], ...] = (
    ("ADANIGAS", date(2020, 6, 1), 2605),   # -> ADANIGAS, not ATGL (469)
    ("ADANITRANS", date(2020, 6, 1), 2606),  # -> ADANITRANS, not ADANIENSOL (440)
    ("AMARAJABAT", date(2020, 6, 1), 2617),  # -> AMARAJABAT, not ARE&M (42)
    ("TATAGLOBAL", date(2019, 12, 2), 2911),  # -> TATAGLOBAL, not TATACONSUM (314)
)


async def main() -> None:
    """Build intervals from real chains and verify period-correct resolution."""
    db = get_database()
    async with db.session() as session:
        rows = (await session.execute(_CHAINS_SQL)).fetchall()

    intervals_by_symbol: dict[str, list[SymbolInterval]] = {}
    for _isin, symbol, sid, listing, delisting in rows:
        intervals_by_symbol.setdefault(symbol.upper(), []).append(
            SymbolInterval(security_id=sid, start=listing, end=delisting)
        )

    results = []
    all_ok = True
    for symbol, on_date, expected_id in _PROBES:
        res = resolve_period_correct(symbol, on_date, intervals_by_symbol)
        ok = res.security_id == expected_id and res.outcome == PeriodResolutionOutcome.CONTAINED
        all_ok = all_ok and ok
        results.append(
            {
                "symbol": symbol,
                "on_date": on_date.isoformat(),
                "expected_id": expected_id,
                "resolved_id": res.security_id,
                "outcome": str(res.outcome),
                "ok": ok,
            }
        )

    # Aggregate outcome census across every chain member's own interval midpoint.
    census: dict[str, int] = {}
    for symbol, intervals in intervals_by_symbol.items():
        for iv in intervals:
            if iv.start is None:
                continue
            probe = iv.start
            outcome = resolve_period_correct(symbol, probe, intervals_by_symbol).outcome
            census[str(outcome)] = census.get(str(outcome), 0) + 1

    print(
        json.dumps(
            {
                "chains_symbols": len(intervals_by_symbol),
                "probes": results,
                "all_probes_ok": all_ok,
                "self_interval_census": census,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
