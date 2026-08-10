"""Re-parse ``corporate_actions.ratio`` from the stored raw subject.

The subject-line parser had two defects. It returned on the bonus leg and
dropped a combined face-value split, and its face-value pattern matched "Rs"
but not NSE's singular "Re" ("To Re 1/-"). Both wrote a wrong or absent ratio.

This repairs the persisted rows in place. It re-runs the fixed
:func:`_parse_corporate_action_ratio` over ``raw->>'subject'``, which every row
already carries, so no network call and no new data source is involved. Same
subject in, same ratio out.

It rewrites ``corporate_actions`` only. It does NOT touch ``ohlcv_daily``.
Live adjusted prices stay as they are until a separate, benchmarked refresh
re-applies them.

Usage:  python scripts/rp014_reparse_corporate_action_ratios.py [--apply]
"""

from __future__ import annotations

import asyncio
import json
import sys

from sqlalchemy import select

from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.models import CorporateActionModel
from momentum25.infrastructure.providers.bhavcopy import (
    _parse_corporate_action_ratio,
)


async def main(apply: bool) -> None:
    """Re-parse every stored action; print a JSON summary of the changes."""
    db = get_database()
    changed = 0
    gained = 0
    lost = 0
    samples: list[dict[str, object]] = []

    async with db.session() as session:
        rows = (await session.execute(select(CorporateActionModel))).scalars().all()
        for row in rows:
            subject = (row.raw or {}).get("subject") or ""
            action_type, ratio = _parse_corporate_action_ratio(subject)
            if ratio == row.ratio and action_type == row.type:
                continue
            changed += 1
            if row.ratio is None and ratio is not None:
                gained += 1
            elif row.ratio is not None and ratio is None:
                lost += 1
            if len(samples) < 10:
                samples.append(
                    {
                        "ex_date": row.ex_date.isoformat(),
                        "subject": subject,
                        "old_type": row.type,
                        "new_type": action_type,
                        "old_ratio": str(row.ratio),
                        "new_ratio": str(ratio),
                    }
                )
            if apply:
                row.type = action_type
                row.ratio = ratio
        if apply:
            await session.commit()

    print(
        json.dumps(
            {
                "applied": apply,
                "rows_scanned": len(rows),
                "rows_changed": changed,
                "ratio_gained": gained,
                "ratio_lost": lost,
                "samples": samples,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main(apply="--apply" in sys.argv))
