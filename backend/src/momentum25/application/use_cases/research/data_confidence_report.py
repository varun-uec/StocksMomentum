"""DataConfidenceReport — per-security Data Confidence Score across the universe.

Computed on demand from the OHLCV repository rather than persisted: the
score is cheap to compute (one bar fetch per security) and nothing else in
the platform currently needs point-in-time historical confidence scores, so
persisting it now would be a speculative abstraction ahead of any real need.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from momentum25.domain.research.data_quality import (
    DataConfidenceScore,
    compute_data_confidence_score,
)


class DataConfidenceReport:
    """Computes Data Confidence Scores for a set of securities over a coverage window."""

    def __init__(self, ohlcv_repo: Any) -> None:
        """Wire the use case with its collaborators."""
        self._ohlcv_repo = ohlcv_repo

    async def execute(
        self, security_ids: list[int], coverage_start: date, coverage_end: date
    ) -> dict[int, DataConfidenceScore]:
        """Return each security's Data Confidence Score for ``[coverage_start, coverage_end]``."""
        lookback_days = (coverage_end - coverage_start).days + 5
        scores: dict[int, DataConfidenceScore] = {}
        for security_id in security_ids:
            series = await self._ohlcv_repo.get_series(
                security_id, lookback_days=lookback_days, as_of=coverage_end
            )
            bars = [b for b in series.bars if b.date >= coverage_start]
            scores[security_id] = compute_data_confidence_score(
                security_id, bars, coverage_start, coverage_end
            )
        return scores
