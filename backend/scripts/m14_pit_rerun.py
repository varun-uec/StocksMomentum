#!/usr/bin/env python3
"""M14.7: re-run a sample of past research through the point-in-time path.

For each sampled stored run it compares three selections on the same date:

1. **stored**: the run as it was saved;
2. **live**: today's historical path (stored ``adj_factor``, today's universe);
3. **pit**: the point-in-time path (factors from actions known by the date,
   the universe listed and not delisted by then).

stored → live is code drift since the run. live → pit is the point-in-time
effect alone. For names that change between live and pit, it counts which
gate rules changed their verdict. Read only; run it against a copy.

Usage:
    M25_DATABASE_URL=...momentum25_e2e python scripts/m14_pit_rerun.py \
        --series adjfix-recheck --strategy-id 8 --sample 8 --out report.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from datetime import date
from typing import Any

from sqlalchemy import select

from momentum25.application.use_cases.research.historical_screening import (
    HistoricalScreeningUseCase,
)
from momentum25.domain.scoring.ranking_engine import RankingEngineImpl
from momentum25.domain.scoring.scoring_engine import ScoringEngineImpl
from momentum25.domain.strategy.bootstrap import register_builtin_engines
from momentum25.domain.strategy.engine_registry import engine_registry
from momentum25.domain.strategy.strategy_engine import StrategyEngine
from momentum25.domain.value_objects.instrument import is_equity
from momentum25.domain.value_objects.results import Ranking, StockScore
from momentum25.infrastructure.calendar.nse_calendar import get_nse_trading_calendar
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.evaluation_market import PointInTimeMarket
from momentum25.infrastructure.persistence.models import (
    ScreeningResultModel,
    ScreeningRunModel,
)
from momentum25.infrastructure.persistence.point_in_time import current_revision
from momentum25.infrastructure.persistence.repositories import (
    SqlOHLCVRepository,
    SqlSecurityRepository,
    SqlStrategyRepository,
)
from momentum25.infrastructure.pipelines.indicator_pipeline import IndicatorPipelineImpl

TOP_N = 25


def _sets(rankings: list[Ranking]) -> tuple[set[int], set[int]]:
    qualified = {r.security_id for r in rankings if r.rank is not None}
    top = {r.security_id for r in rankings if r.rank is not None and r.rank <= TOP_N}
    return qualified, top


def _jaccard(a: set[int], b: set[int]) -> float:
    return len(a & b) / len(a | b) if a | b else 1.0


def _verdicts(score: StockScore) -> dict[str, bool]:
    return {rr.rule_id: rr.passed for er in score.engine_results for rr in er.rule_results}


async def main(series: str, strategy_id: int, sample: int) -> dict[str, Any]:
    """Compare stored, live and point-in-time selections on ``sample`` run dates."""
    register_builtin_engines()
    engine = StrategyEngine(
        engines=engine_registry, scoring=ScoringEngineImpl(), ranking=RankingEngineImpl()
    )
    async with get_database().session() as session:
        strategy = next(
            s for s in await SqlStrategyRepository(session).list() if s.id == strategy_id
        )
        gates = strategy.config.gate_rule_ids()
        runs = (
            await session.scalars(
                select(ScreeningRunModel)
                .where(
                    ScreeningRunModel.strategy_id == strategy_id,
                    ScreeningRunModel.data_version.like(f"historical:%:{series}"),
                    ScreeningRunModel.status == "COMPLETED",
                )
                .order_by(ScreeningRunModel.run_date)
            )
        ).all()
        step = max(1, (len(runs) - 1) // (sample - 1)) if sample > 1 else len(runs)
        picked = runs[::step][:sample]
        revision = await current_revision(session)
        market = PointInTimeMarket(session, revision, get_nse_trading_calendar(), 120)
        live_use_case = HistoricalScreeningUseCase(
            security_repo=None,
            ohlcv_repo=SqlOHLCVRepository(session),
            screening_run_repo=None,
            strategy_repo=None,
            indicator_pipeline=IndicatorPipelineImpl(session),
            strategy_engine=engine,
        )
        everyone = await SqlSecurityRepository(session).list_active()
        rows: list[dict[str, Any]] = []
        causes: Counter[str] = Counter()
        for run in picked:
            day: date = run.run_date
            stored = [
                Ranking(r.security_id, r.momentum_score, r.buy_setup_score, r.rank)
                for r in await session.scalars(
                    select(ScreeningResultModel).where(ScreeningResultModel.run_id == run.id)
                )
            ]
            universe = [
                s
                for s in everyone
                if is_equity(s.isin) and (s.listing_date is None or s.listing_date <= day)
            ]
            live_scores, live_rank, _ = await live_use_case.screen(strategy, day, universe)
            pit_scores, pit_rank, symbols = await market.screen(strategy, day)
            (sq, st), (lq, lt), (pq, pt) = _sets(stored), _sets(live_rank), _sets(pit_rank)
            live_by_id = {s.security_id: s for s in live_scores}
            pit_by_id = {s.security_id: s for s in pit_scores}
            for sid in lq ^ pq:
                if sid not in live_by_id or sid not in pit_by_id:
                    causes["universe (screened by one path only)"] += 1
                    continue
                live_v, pit_v = _verdicts(live_by_id[sid]), _verdicts(pit_by_id[sid])
                changed = sorted(r for r in gates if live_v.get(r) != pit_v.get(r))
                for rule in changed or ["no gate verdict changed"]:
                    causes[rule] += 1
            rows.append(
                {
                    "date": day.isoformat(),
                    "run_id": run.id,
                    "qualified": {"stored": len(sq), "live": len(lq), "pit": len(pq)},
                    "jaccard_qualified": {
                        "stored_live": round(_jaccard(sq, lq), 3),
                        "live_pit": round(_jaccard(lq, pq), 3),
                    },
                    "top_overlap": {"stored_live": len(st & lt), "live_pit": len(lt & pt)},
                    "only_live": sorted(symbols.get(i, str(i)) for i in lq - pq)[:15],
                    "only_pit": sorted(symbols.get(i, str(i)) for i in pq - lq)[:15],
                }
            )
            print(json.dumps(rows[-1]), flush=True)
        return {
            "series": series,
            "strategy_id": strategy_id,
            "revision": revision,
            "runs": rows,
            "causes": dict(causes.most_common()),
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--series", default="adjfix-recheck")
    parser.add_argument("--strategy-id", type=int, default=8)
    parser.add_argument("--sample", type=int, default=8)
    parser.add_argument("--out", default="m14_pit_rerun.json")
    args = parser.parse_args()
    report = asyncio.run(main(args.series, args.strategy_id, args.sample))
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps(report["causes"], indent=2))
