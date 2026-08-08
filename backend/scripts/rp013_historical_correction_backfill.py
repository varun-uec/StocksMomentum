"""RP-013 — pre-2019 historical screening layer for the six correction windows.

Generates deterministic historical screening runs (screening_runs, rule_results,
screening_results, forward_returns) for the six correction regimes that RP-005 /
RP-006 need but which the live tables (2019-10-01+) do not cover, by pointing the
*frozen production strategy* (``minervini_trend_template``, strategy_id=30,
version 3, config_hash d1e0e42…) and the *existing* screening/scoring pipeline at
the ``legacy_ohlcv_daily`` archive instead of the live ``ohlcv_daily``.

Nothing about methodology is invented here:

* Universe: reconstructed per run date from the legacy archive using the frozen,
  confirmed-sound liquidity floor ``L`` (``HistoricalUniverseReconstruction`` /
  ``liquidity_floor.py`` — untouched).
* Scoring: the same ``StrategyEngine`` / ``ScoringEngineImpl`` /
  ``RankingEngineImpl`` and the same ``IndicatorPipelineImpl`` formulas the live
  daily runs use, via ``HistoricalScreeningUseCase`` — only the bar-source table
  differs (``LegacyIndicatorPipelineImpl`` / ``LegacyBackedOHLCVRepository``).
* Forward returns: the existing ``ForwardReturnsBackfill``, pointed at the legacy
  archive, at the 20/60/120-day horizons, computed only where the legacy data's
  own range supplies the bars (never fabricated).

Standing contamination pre-filter (Research Dataset v1.0 §86: SINGLE fixture,
NULL-ISIN names, ETF heuristic hits) is applied at generation time. Every run is
tagged ``historical:<date>:legacy-backfill:<regime>`` (so it is excluded from all
product-facing queries by the existing ``historical:%`` filter) and carries a
``run_type=historical_backfill`` stat plus the survivorship disclosure, so these
rows can never be confused with live production screening.

Determinism: identical inputs → identical outputs. The run is resumable — a
(date, regime) whose run already exists is skipped — so re-invocation is safe.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from structlog import get_logger

from momentum25.application.use_cases.research.forward_returns_backfill import (
    ForwardReturnsBackfill,
)
from momentum25.application.use_cases.research.historical_screening import (
    HistoricalScreeningUseCase,
)
from momentum25.application.use_cases.research.historical_universe_reconstruction import (
    HistoricalUniverseReconstruction,
)
from momentum25.domain.entities.security import Security
from momentum25.domain.scoring.ranking_engine import RankingEngineImpl
from momentum25.domain.scoring.scoring_engine import ScoringEngineImpl
from momentum25.domain.strategy.bootstrap import register_builtin_engines
from momentum25.domain.strategy.engine_registry import engine_registry
from momentum25.domain.strategy.strategy_engine import StrategyEngine
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.models import ScreeningRunModel
from momentum25.infrastructure.persistence.repositories import (
    SqlScreeningRunRepository,
    SqlSecurityRepository,
    SqlStrategyRepository,
)
from momentum25.infrastructure.persistence.repositories.historical_backfill import (
    SqlHistoricalUniverseRepository,
    SqlLegacyOHLCVRepository,
)
from momentum25.infrastructure.persistence.repositories.legacy_backed_ohlcv import (
    LegacyBackedOHLCVRepository,
)
from momentum25.infrastructure.pipelines.indicator_pipeline import (
    LegacyIndicatorPipelineImpl,
)

_logger = get_logger("rp013_historical_correction_backfill")

# The frozen production strategy. ``get_active`` resolves this name to the
# highest version (version 3 = strategy_id=30), i.e. the live production config.
STRATEGY_NAME = "minervini_trend_template"

# Forward-return horizons RP-005/RP-006 require (20/60/120d). Computed only where
# the legacy archive supplies the bars; shorter windows near a window's tail
# simply produce fewer horizons — never fabricated.
FORWARD_HORIZONS: tuple[int, ...] = (20, 60, 120)


@dataclass(frozen=True)
class CorrectionWindow:
    """A named correction regime and its (peak→trough-ish) span.

    Boundaries are transparent, auditable constants using the widely-accepted
    Indian-market episode dates for each named regime (Gate 4c confirmed each
    clears the ≥200-security floor). They live here as a single source of truth
    so research can adjust them without code archaeology; they are *not* a
    methodology decision — only the sampling span for the screening layer.
    """

    regime: str
    start: date
    end: date


CORRECTION_WINDOWS: tuple[CorrectionWindow, ...] = (
    CorrectionWindow("2000_dotcom", date(2000, 2, 14), date(2001, 9, 21)),
    CorrectionWindow("2008_gfc", date(2008, 1, 8), date(2009, 3, 9)),
    CorrectionWindow("2011", date(2011, 1, 3), date(2011, 12, 20)),
    CorrectionWindow("2013_taper_tantrum", date(2013, 5, 20), date(2013, 9, 3)),
    CorrectionWindow("2015_16", date(2015, 3, 4), date(2016, 2, 29)),
    CorrectionWindow("2018_midcap_crash", date(2018, 1, 15), date(2018, 10, 26)),
)

# Production's live cadence is irregular (median gap ~2 weeks). Per the task
# directive we replicate a clean weekly grid — denser than production, i.e.
# conservative, and enough per-year depth for a per-year stratified IC test
# without an exhaustive daily backtest.
_CADENCE = timedelta(days=7)


def weekly_run_dates(
    window: CorrectionWindow, trading_dates: list[date]
) -> list[date]:
    """Return the weekly-grid run dates for ``window`` snapped to legacy sessions.

    Steps weekly from the window start; each target is snapped back to the latest
    legacy trading date ``<= target`` that still lies inside the window. Pure and
    deterministic. ``trading_dates`` must be ascending.
    """
    if not trading_dates:
        return []
    in_window = [d for d in trading_dates if window.start <= d <= window.end]
    if not in_window:
        return []
    out: list[date] = []
    seen: set[date] = set()
    target = window.start
    while target <= window.end:
        candidates = [d for d in in_window if d <= target]
        if candidates:
            snapped = candidates[-1]
            if snapped not in seen:
                seen.add(snapped)
                out.append(snapped)
        target += _CADENCE
    return out


def is_contaminated(security: Security) -> bool:
    """Standing contamination pre-filter (Research Dataset v1.0 §86).

    Excludes the ``SINGLE`` test fixture, NULL-ISIN names, and ETF heuristic hits
    (symbol/name matching ``ETF``) — the exact heuristic already used by the
    RP-012 backfill scripts. Matching is case-insensitive.
    """
    symbol = str(security.symbol).upper()
    name = (security.name or "").upper()
    if symbol == "SINGLE":
        return True
    if security.isin is None:
        return True
    if "ETF" in symbol or "ETF" in name:  # noqa: SIM103
        return True
    return False


def _data_version(run_date: date, regime: str) -> str:
    """Deterministic, tagged ``data_version`` for a (date, regime) backfill run."""
    return f"historical:{run_date.isoformat()}:legacy-backfill:{regime}"


async def _existing_run_dates(session: Any, regime: str) -> set[date]:
    """Return run dates already backfilled for ``regime`` (for resumability)."""
    prefix = f"historical:%:legacy-backfill:{regime}"
    result = await session.execute(
        select(ScreeningRunModel.run_date).where(
            ScreeningRunModel.data_version.like(prefix)
        )
    )
    return set(result.scalars().all())


async def _run_one_date(
    *,
    run_date: date,
    window: CorrectionWindow,
    securities_by_id: dict[int, Security],
    recon: HistoricalUniverseReconstruction,
    screening_use_case: HistoricalScreeningUseCase,
    forward_backfill: ForwardReturnsBackfill,
    screening_run_repo: SqlScreeningRunRepository,
) -> dict[str, int]:
    """Reconstruct the universe, screen, tag, and backfill forward returns for a date."""
    memberships = await recon.reconstruct_date(run_date)
    eligible_symbols: list[str] = []
    for m in memberships:
        if not m.eligible:
            continue
        sec = securities_by_id.get(m.security_id)
        if sec is None or is_contaminated(sec):
            continue
        eligible_symbols.append(str(sec.symbol))

    if not eligible_symbols:
        _logger.warning("no_eligible_symbols", run_date=run_date.isoformat())
        return {"screened": 0, "forward_rows": 0}

    result = await screening_use_case.execute(
        strategy_name=STRATEGY_NAME,
        as_of_date=run_date,
        symbol_filter=eligible_symbols,
        run_suffix=f":legacy-backfill:{window.regime}",
        # The reconstructed legacy universe is already point-in-time correct
        # (real bars dated ≤ run_date); the provider-coverage-start listing_date
        # would otherwise wrongly drop names that demonstrably traded that day.
        enforce_listing_date_filter=False,
    )
    run_id = int(result["run_id"])

    # Enrich the run's stats so it is unmistakably a legacy historical backfill.
    run = await screening_run_repo.get(run_id)
    if run is not None:
        run.stats = {
            **(run.stats or {}),
            "run_type": "historical_backfill",
            "regime": window.regime,
            "bar_source": "legacy_ohlcv_daily",
            "cadence": "weekly",
            "strategy_name": STRATEGY_NAME,
            "contamination_prefilter": "SINGLE|NULL_ISIN|ETF",
        }
        await screening_run_repo.update(run)
        await screening_run_repo._session.commit()  # noqa: SLF001

    fr = await forward_backfill.execute(run_id)
    return {
        "screened": int(result["total_evaluated"]),
        "passed": int(result["total_passed"]),
        "forward_rows": int(fr["rows_written"]),
    }


async def main() -> None:
    """Run the full six-regime historical backfill."""
    register_builtin_engines()
    db = get_database()

    async with db.session() as session:
        legacy_repo = SqlLegacyOHLCVRepository(session)
        # Full legacy trading-date calendar (one query, reused for every window).
        trading_dates = await legacy_repo.distinct_dates(date(1994, 1, 1), date(2024, 12, 31))

        security_repo = SqlSecurityRepository(session)
        securities_by_id = {
            s.id: s for s in await security_repo.list_all() if s.id is not None
        }

    summary: dict[str, Any] = {}
    for window in CORRECTION_WINDOWS:
        run_dates = weekly_run_dates(window, trading_dates)
        regime_summary = {
            "planned_dates": len(run_dates),
            "screened_dates": 0,
            "skipped_existing": 0,
            "forward_rows": 0,
        }

        # Each date gets its own unit-of-work session/transaction so a failure
        # on one date never poisons another (and commits stay bounded).
        async with db.session() as session:
            existing = await _existing_run_dates(session, window.regime)

        for run_date in run_dates:
            if run_date in existing:
                regime_summary["skipped_existing"] += 1
                continue
            async with db.session() as session:
                universe_repo = SqlHistoricalUniverseRepository(session)
                recon = HistoricalUniverseReconstruction(
                    SqlLegacyOHLCVRepository(session), universe_repo
                )
                legacy_ohlcv = LegacyBackedOHLCVRepository(session)
                screening_run_repo = SqlScreeningRunRepository(session)
                strategy_engine = StrategyEngine(
                    engines=engine_registry,
                    scoring=ScoringEngineImpl(),
                    ranking=RankingEngineImpl(),
                )
                screening_use_case = HistoricalScreeningUseCase(
                    security_repo=SqlSecurityRepository(session),
                    ohlcv_repo=legacy_ohlcv,
                    screening_run_repo=screening_run_repo,
                    strategy_repo=SqlStrategyRepository(session),
                    indicator_pipeline=LegacyIndicatorPipelineImpl(session),
                    strategy_engine=strategy_engine,
                )
                forward_backfill = ForwardReturnsBackfill(
                    screening_run_repo=screening_run_repo,
                    ohlcv_repo=legacy_ohlcv,
                    horizons=FORWARD_HORIZONS,
                )
                res = await _run_one_date(
                    run_date=run_date,
                    window=window,
                    securities_by_id=securities_by_id,
                    recon=recon,
                    screening_use_case=screening_use_case,
                    forward_backfill=forward_backfill,
                    screening_run_repo=screening_run_repo,
                )
                regime_summary["screened_dates"] += 1
                regime_summary["forward_rows"] += res["forward_rows"]
            _logger.info(
                "backfill_date_done",
                regime=window.regime,
                run_date=run_date.isoformat(),
                **res,
            )

        summary[window.regime] = regime_summary
        _logger.info("regime_done", regime=window.regime, **regime_summary)

    import json

    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
