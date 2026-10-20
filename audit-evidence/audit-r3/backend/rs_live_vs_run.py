"""Driver (imports production code): RS universe of /stocks/{s}/live vs the screening run.

The run ranks RS across active equities (ISIN not INF*); the live/watchlist path
(resolve_universe_rs_ratings) ranks across every active security. Same date, same data.
"""
import asyncio
import json
from datetime import date

from momentum25.application.services.rs_ratings import compute_universe_rs_ratings
from momentum25.domain.value_objects.instrument import is_equity
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.repositories import SqlOHLCVRepository, SqlSecurityRepository

W = {"63": 0.4, "126": 0.2, "189": 0.2, "252": 0.2}


async def main() -> None:
    async with get_database().session() as s:
        active = await SqlSecurityRepository(s).list_active()
        ohlcv = SqlOHLCVRepository(s)
        d = date(2026, 10, 19)
        live = await compute_universe_rs_ratings(active, ohlcv, d, W)
        run = await compute_universe_rs_ratings([x for x in active if is_equity(x.isin)], ohlcv, d, W)
        common = [k for k in run if k in live]
        diff = [k for k in common if run[k] != live[k]]
        cross = [k for k in common if (run[k] >= 70) != (live[k] >= 70)]
        print(json.dumps({"live_universe": len(live), "run_universe": len(run),
                          "RELIANCE": {"run": run.get("RELIANCE"), "live": live.get("RELIANCE")},
                          "equities_with_different_rating": len(diff),
                          "rs70_gate_crossings": len(cross), "crossing_examples": cross[:10]}))


asyncio.run(main())
