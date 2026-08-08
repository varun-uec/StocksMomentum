"""OverlapReconciliationReport — Gate 4a (RP-012 Phase 2 §2).

Joins legacy-staging bars against live current-provider bars on
``(security_id, date)`` for every trading date in the overlap window and folds
them through the pure :mod:`domain.research.overlap_reconciliation` tally to
produce the three research-specified match rates and an explained mismatch
classification. Reads only — this is the canary gate and writes nothing.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from structlog import get_logger

from momentum25.application.use_cases.research.legacy_overlap_backfill import (
    OVERLAP_END,
    OVERLAP_START,
)
from momentum25.domain.research.overlap_reconciliation import ReconciliationTally

_logger = get_logger("overlap_reconciliation")


class OverlapReconciliationReport:
    """Computes the Gate 4a reconciliation report over the overlap window."""

    def __init__(self, legacy_repo: Any, ohlcv_repo: Any) -> None:
        """Wire the use case with the legacy staging and live OHLCV repositories."""
        self._legacy_repo = legacy_repo
        self._ohlcv_repo = ohlcv_repo

    async def execute(
        self, start: date = OVERLAP_START, end: date = OVERLAP_END
    ) -> dict[str, object]:
        """Reconcile every legacy trading date in ``[start, end]``; return the report."""
        tally = ReconciliationTally()
        for on_date in await self._legacy_repo.distinct_dates(start, end):
            legacy_bars = await self._legacy_repo.bars_by_security_on(on_date)
            current_bars = await self._ohlcv_repo.bars_by_security_on(on_date)
            tally.add_date(
                {str(k): v for k, v in legacy_bars.items()},
                {str(k): v for k, v in current_bars.items()},
                date_label=on_date.isoformat(),
            )

        report = tally.to_report()
        _logger.info(
            "overlap_reconciliation_completed",
            gate_passes=report["gate_passes"],
            dates=report["dates_processed"],
            pairs=report["joined_pairs"],
        )
        return report
