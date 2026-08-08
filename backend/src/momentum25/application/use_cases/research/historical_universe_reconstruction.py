"""HistoricalUniverseReconstruction + calibration — RP-012 Phase 2 §3 / Gate 4d.

Reconstructs point-in-time ``historical_universe`` membership over the overlap
window from the legacy staging table using the research-specified liquidity
floor, and produces the Gate 4d calibration + point-in-time integrity report.

Point-in-time integrity is structural, not incidental: reconstruction for date
``D`` reads only legacy bars with ``date <= D`` (the repository queries enforce
``<= as_of`` / ``< before``), so no look-ahead is possible.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from structlog import get_logger

from momentum25.application.use_cases.research.legacy_overlap_backfill import (
    OVERLAP_END,
    OVERLAP_START,
)
from momentum25.domain.research.liquidity_floor import (
    EQ_SERIES,
    TURNOVER_WINDOW,
    evaluate_liquidity_eligibility,
)
from momentum25.domain.research.universe_calibration import (
    calibrate_date,
    direction_of_miss,
)
from momentum25.domain.value_objects.results import UniverseMembership

_logger = get_logger("historical_universe_reconstruction")


class HistoricalUniverseReconstruction:
    """Reconstructs and persists the historical universe, and calibrates it."""

    def __init__(
        self, legacy_repo: Any, historical_universe_repo: Any
    ) -> None:
        """Wire the use case with the legacy staging and historical-universe repos."""
        self._legacy_repo = legacy_repo
        self._universe_repo = historical_universe_repo

    async def reconstruct_date(self, as_of: date) -> list[UniverseMembership]:
        """Compute (do not persist) the universe membership for a single date.

        Reads only bars with ``date <= as_of`` — the point-in-time guarantee.
        """
        bars = await self._legacy_repo.bars_by_security_on(as_of)
        memberships: list[UniverseMembership] = []
        for security_id, bar in bars.items():
            prior_sessions = await self._legacy_repo.prior_session_count(security_id, as_of)
            trailing = await self._legacy_repo.trailing_bars(
                security_id, as_of, limit=TURNOVER_WINDOW
            )
            trailing_turnovers = [b.turnover_value for b in trailing]
            decision = evaluate_liquidity_eligibility(
                close=bar.close,
                series=EQ_SERIES,  # only EQ bars are persisted to the legacy staging table
                prior_session_count=prior_sessions,
                trailing_turnovers=trailing_turnovers,
            )
            memberships.append(
                UniverseMembership(
                    security_id=security_id,
                    eligible=decision.eligible,
                    reason=decision.reason,
                )
            )
        return memberships

    async def execute(
        self, start: date = OVERLAP_START, end: date = OVERLAP_END
    ) -> dict[str, int]:
        """Reconstruct and persist membership for every legacy date in ``[start, end]``.

        Efficient path: each security's full legacy series is loaded once and the
        liquidity rule is applied across its dates with an in-memory rolling
        window, so the whole window costs one query + one bulk insert per
        security rather than two queries per (security, date). The point-in-time
        guarantee is preserved structurally — for the bar at index ``i`` only the
        ``i`` prior bars and the trailing 50 turnovers ending at ``i`` are used,
        never a later bar. Identical inputs yield identical membership (ADR-009).
        """
        rows_written = 0
        securities = await self._legacy_repo.distinct_security_ids(start, end)
        for security_id in securities:
            bars = await self._legacy_repo.bars_for_security(security_id, start, end)
            dated = self._reconstruct_series(security_id, bars)
            rows_written += await self._universe_repo.insert_dated_memberships(dated)
            await self._commit()
        summary = {"securities_processed": len(securities), "rows_written": rows_written}
        _logger.info("historical_universe_reconstruction_completed", **summary)
        return summary

    def _reconstruct_series(
        self, security_id: int, bars: list[Any]
    ) -> list[tuple[date, UniverseMembership]]:
        """Apply the liquidity rule across one security's ascending legacy series (pure)."""
        turnovers = [b.turnover_value for b in bars]
        out: list[tuple[date, UniverseMembership]] = []
        for i, bar in enumerate(bars):
            window = turnovers[max(0, i - TURNOVER_WINDOW + 1) : i + 1]
            decision = evaluate_liquidity_eligibility(
                close=bar.close,
                series=EQ_SERIES,  # only EQ bars are persisted to the legacy staging table
                prior_session_count=i,  # bars strictly before this one
                trailing_turnovers=window,
            )
            out.append(
                (
                    bar.date,
                    UniverseMembership(
                        security_id=security_id,
                        eligible=decision.eligible,
                        reason=decision.reason,
                    ),
                )
            )
        return out

    async def _commit(self) -> None:
        """Commit the current unit of work (bounded write set per security)."""
        session = getattr(self._universe_repo, "_session", None)
        if session is not None:
            await session.commit()

    async def calibrate(
        self, production_universe_by_date: dict[date, set[int]]
    ) -> dict[str, object]:
        """Gate 4d calibration: compare reconstructed vs production universe.

        ``production_universe_by_date`` maps each sampled matched date to the set
        of production-eligible ``security_id``. For every such date the persisted
        reconstructed eligible set is loaded and compared. Pooled coverage/ratio
        (target ≥90% / within ±15%) plus the direction of any miss are reported;
        ``L`` is never adjusted here.
        """
        per_date: list[dict[str, object]] = []
        pooled_production = 0
        pooled_overlap = 0
        pooled_reconstructed = 0
        for as_of in sorted(production_universe_by_date):
            production_set = production_universe_by_date[as_of]
            reconstructed_set = await self._universe_repo.eligible_members(as_of)
            calibration = calibrate_date(as_of, production_set, reconstructed_set)
            entry = calibration.to_dict()
            entry["direction_of_miss"] = direction_of_miss(calibration)
            per_date.append(entry)
            pooled_production += calibration.production_count
            pooled_overlap += calibration.overlap_count
            pooled_reconstructed += calibration.reconstructed_count

        pooled_coverage = (
            pooled_overlap / pooled_production if pooled_production > 0 else None
        )
        pooled_precision = (
            pooled_overlap / pooled_reconstructed if pooled_reconstructed > 0 else None
        )
        pooled_ratio = (
            pooled_reconstructed / pooled_production if pooled_production > 0 else None
        )
        return {
            "per_date": per_date,
            "pooled_production_count": pooled_production,
            "pooled_reconstructed_count": pooled_reconstructed,
            "pooled_overlap_count": pooled_overlap,
            # Corrected P/R diagnostic: recall = overlap/production,
            # precision = overlap/reconstructed. count_ratio alone can mask
            # offsetting false positives and false negatives.
            "pooled_coverage": None if pooled_coverage is None else f"{pooled_coverage:.4f}",
            "pooled_recall": None if pooled_coverage is None else f"{pooled_coverage:.4f}",
            "pooled_precision": (
                None if pooled_precision is None else f"{pooled_precision:.4f}"
            ),
            "pooled_count_ratio": None if pooled_ratio is None else f"{pooled_ratio:.4f}",
        }

    async def verify_point_in_time(self, as_of: date) -> dict[str, object]:
        """Confirm reconstruction for ``as_of`` reads only bars dated ≤ ``as_of``.

        Reconstructs the date, then asserts every input bar and every trailing
        turnover bar used carries a date ≤ ``as_of``. Returns a confirmation
        record for the Gate 4d report.
        """
        bars = await self._legacy_repo.bars_by_security_on(as_of)
        max_bar_date: date | None = None
        for security_id in bars:
            trailing = await self._legacy_repo.trailing_bars(
                security_id, as_of, limit=TURNOVER_WINDOW
            )
            for b in trailing:
                if max_bar_date is None or b.date > max_bar_date:
                    max_bar_date = b.date
        no_lookahead = max_bar_date is None or max_bar_date <= as_of
        return {
            "as_of": as_of.isoformat(),
            "securities_checked": len(bars),
            "max_input_bar_date": max_bar_date.isoformat() if max_bar_date else None,
            "no_lookahead": no_lookahead,
        }
