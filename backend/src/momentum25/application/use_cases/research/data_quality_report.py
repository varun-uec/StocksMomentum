"""DataQualityReport — orchestrates data-quality checks against persisted history.

Cross-references detected price anomalies against persisted corporate
actions so a real split/bonus isn't reported as a data defect (see
``domain.research.data_quality.detect_price_anomalies``).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from structlog import get_logger

from momentum25.domain.research.data_quality import (
    DataQualityIssue,
    detect_duplicates,
    detect_gaps,
    detect_price_anomalies,
    detect_volume_anomalies,
)

_logger = get_logger("data_quality_report")

# A price anomaly is considered "explained" by a corporate action whose
# ex_date falls within this many calendar days -- disclosure dates and bhavcopy
# posting can be off by a day or two around weekends/settlement.
_CORPORATE_ACTION_TOLERANCE_DAYS = 3


class DataQualityReport:
    """Runs the full data-quality check suite for one security over a date range."""

    def __init__(self, ohlcv_repo: Any, corporate_action_repo: Any) -> None:
        """Wire the use case with its collaborators."""
        self._ohlcv_repo = ohlcv_repo
        self._corporate_action_repo = corporate_action_repo

    async def execute(self, security_id: int, start: date, end: date) -> dict[str, Any]:
        """Return a structured data-quality report for ``security_id`` over ``[start, end]``."""
        lookback_days = (end - start).days + 5
        series = await self._ohlcv_repo.get_series(
            security_id, lookback_days=lookback_days, as_of=end
        )
        bars = [b for b in series.bars if b.date >= start]

        gaps = detect_gaps([b.date for b in bars], start, end)
        duplicates = detect_duplicates(bars)
        price_anomalies = detect_price_anomalies(bars)
        volume_anomalies = detect_volume_anomalies(bars)

        actions = await self._corporate_action_repo.list_for_security(security_id)
        action_dates = [a.ex_date for a in actions]

        unexplained_price_anomalies = [
            issue
            for issue in price_anomalies
            if not self._explained_by_corporate_action(issue, action_dates)
        ]

        report = {
            "security_id": security_id,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "bars_found": len(bars),
            "gaps": [self._issue_dict(i) for i in gaps],
            "duplicates": [self._issue_dict(i) for i in duplicates],
            "price_anomalies_total": len(price_anomalies),
            "price_anomalies_explained_by_corporate_action": (
                len(price_anomalies) - len(unexplained_price_anomalies)
            ),
            "unexplained_price_anomalies": [
                self._issue_dict(i) for i in unexplained_price_anomalies
            ],
            "volume_anomalies": [self._issue_dict(i) for i in volume_anomalies],
            "trading_calendar_disclosure": (
                "Gaps are computed against an approximated weekday-only trading "
                "calendar -- no free NSE holiday calendar source exists, so a real "
                "exchange holiday will appear as a false-positive gap here."
            ),
        }
        _logger.info(
            "data_quality_report_completed",
            security_id=security_id,
            gaps=len(gaps),
            duplicates=len(duplicates),
            unexplained_price_anomalies=len(unexplained_price_anomalies),
        )
        return report

    @staticmethod
    def _explained_by_corporate_action(
        issue: DataQualityIssue, action_dates: list[date]
    ) -> bool:
        return any(
            abs((issue.issue_date - action_date).days) <= _CORPORATE_ACTION_TOLERANCE_DAYS
            for action_date in action_dates
        )

    @staticmethod
    def _issue_dict(issue: DataQualityIssue) -> dict[str, str]:
        return {
            "issue_type": issue.issue_type,
            "date": issue.issue_date.isoformat(),
            "detail": issue.detail,
        }
