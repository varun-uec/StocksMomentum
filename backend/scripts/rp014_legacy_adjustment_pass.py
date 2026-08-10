"""RP-014 follow-up — apply backward price adjustment to the legacy tables.

Reads the persisted ``corporate_actions`` and writes ``adj_factor`` /
``adj_close`` on ``legacy_ohlcv_daily`` and ``bse_legacy_ohlcv_daily``.

The factor maths is NOT reimplemented here. It reuses
:func:`momentum25.domain.entities.market_data.compute_adjustment_factors`, the
same function the live ``ohlcv_daily`` path uses, so legacy and live
adjustment semantics are identical by construction.

No network calls. Actions come from the database only, already deduplicated by
``SqlCorporateActionRepository.save_many`` and by the ``(security_id, ex_date,
type)`` unique key that ``list_for_security`` reads through.

Known limit, not fixable here: ``corporate_actions`` starts 2011-01-06 because
NSE's free API caps at 20 rows per symbol. Bars before that carry no action
data, so they keep ``adj_factor = 1``. The dot-com and GFC windows stay
unadjusted.

Usage:  python scripts/rp014_legacy_adjustment_pass.py
"""

from __future__ import annotations

import asyncio
import json
from datetime import date

from momentum25.domain.entities.market_data import compute_adjustment_factors
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.models import (
    BSELegacyOHLCVDailyModel,
    LegacyOHLCVDailyModel,
)
from momentum25.infrastructure.persistence.repositories.corporate_actions import (
    SqlCorporateActionRepository,
)
from momentum25.infrastructure.persistence.repositories.historical_backfill import (
    SqlLegacyOHLCVRepository,
)

_MODELS = {
    "legacy_ohlcv_daily": LegacyOHLCVDailyModel,
    "bse_legacy_ohlcv_daily": BSELegacyOHLCVDailyModel,
}

# Wide enough to cover both tables in full (NSE from 1994-11-03, BSE from
# 2006-03-01), so the pass never silently skips an era.
_MIN_DATE = date(1990, 1, 1)
_MAX_DATE = date(2030, 1, 1)


async def main() -> None:
    """Apply adjustment factors to both legacy tables; print a JSON summary."""
    db = get_database()
    summary: dict[str, dict[str, int]] = {}

    for table_name, model in _MODELS.items():
        securities_adjusted = 0
        bars_updated = 0
        async with db.session() as session:
            action_repo = SqlCorporateActionRepository(session)
            repo = SqlLegacyOHLCVRepository(session, model_cls=model)
            security_ids = await repo.distinct_security_ids(
                start=_MIN_DATE, end=_MAX_DATE
            )

            for security_id in security_ids:
                actions = await action_repo.list_for_security(security_id)
                if not any(a.ratio is not None for a in actions):
                    continue
                bars = await repo.bars_for_security(
                    security_id, start=_MIN_DATE, end=_MAX_DATE
                )
                if not bars:
                    continue
                factors = compute_adjustment_factors([b.date for b in bars], actions)
                # Write every bar, including the factor-1 ones on and after the
                # last ex-date. Skipping them would leave adj_close null there,
                # and readers fall back to raw close on null -- so an adjusted
                # bar would be compared against a raw one and the split gap
                # would reappear. The live path writes every factor too.
                bars_updated += await repo.update_adjustment_factors(
                    security_id, factors
                )
                securities_adjusted += 1

        summary[table_name] = {
            "securities_scanned": len(security_ids),
            "securities_adjusted": securities_adjusted,
            "bars_updated": bars_updated,
        }

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
