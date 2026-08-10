"""Re-apply backward price adjustment to ``ohlcv_daily`` after the ratio-parser fix.

The parser fix corrected 232 ``corporate_actions`` ratios (bonus legs that
dropped a combined face-value split, and splits phrased "To Re 1/-"). Those
rows are already repaired in the database by
``rp014_reparse_corporate_action_ratios.py``. Live adjusted prices still carry
the old, wrong factors. This pass recomputes them.

Scope is deliberate: only the securities whose ratios actually changed. Every
other security's actions are byte-identical to before, so recomputing them
would be a no-op — restricting the pass makes any change outside this set a
detectable defect rather than expected churn.

The factor maths is NOT reimplemented. It reuses
:func:`momentum25.domain.entities.market_data.compute_adjustment_factors` and
``SqlOHLCVRepository.update_adjustment_factors``, the same pair the scheduled
``refresh_adjustment_factors`` service uses, so this pass and the live path
cannot drift. No network call: actions come from the database only.

Usage:  python scripts/rp014_reapply_live_adjustment.py --ids-file <json> [--apply]
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date

from momentum25.domain.entities.market_data import compute_adjustment_factors
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.repositories.corporate_actions import (
    SqlCorporateActionRepository,
)
from momentum25.infrastructure.persistence.repositories.ohlcv import SqlOHLCVRepository

# Bounded rather than unlimited, matching the corporate-actions service, so the
# LIMIT-based ``get_series`` query keeps its planner semantics.
_MAX_LOOKBACK_DAYS = 10_000
_AS_OF = date(2030, 1, 1)


async def main(ids: list[int], apply: bool) -> None:
    """Recompute adjustment factors for ``ids``; print a JSON summary."""
    db = get_database()
    securities_adjusted = 0
    bars_updated = 0
    skipped_no_actions = 0
    skipped_no_bars = 0

    async with db.session() as session:
        action_repo = SqlCorporateActionRepository(session)
        ohlcv_repo = SqlOHLCVRepository(session)

        for security_id in ids:
            actions = await action_repo.list_for_security(security_id)
            if not any(a.ratio is not None for a in actions):
                skipped_no_actions += 1
                continue
            series = await ohlcv_repo.get_series(
                security_id, lookback_days=_MAX_LOOKBACK_DAYS, as_of=_AS_OF
            )
            if not series.bars:
                skipped_no_bars += 1
                continue
            factors = compute_adjustment_factors(
                [b.date for b in series.bars], actions
            )
            bars_updated += await ohlcv_repo.update_adjustment_factors(
                security_id, factors
            )
            securities_adjusted += 1

        if apply:
            await session.commit()
        else:
            await session.rollback()

    print(
        json.dumps(
            {
                "applied": apply,
                "securities_requested": len(ids),
                "securities_adjusted": securities_adjusted,
                "skipped_no_actions": skipped_no_actions,
                "skipped_no_bars": skipped_no_bars,
                "bars_updated": bars_updated,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids-file", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    with open(args.ids_file) as fh:
        payload = json.load(fh)
    asyncio.run(main(sorted({int(r["security_id"]) for r in payload}), args.apply))
