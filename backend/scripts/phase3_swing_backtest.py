"""One-off runner for the Phase 3.3 swing target/stop walk-forward backtest.

Read-only against the real ``momentum25`` database (not the throwaway test
DB): runs SwingTargetBacktestUseCase across the full available history of
completed runs for the active ``minervini_trend_template`` strategy, then
again restricted to a genuine hold-out fold (the most recent slice, not used
to derive any of the fixed ATR-multiple constants -- those are conventional,
not fitted). Prints both reports. Not part of the test suite; kept for
reproducibility of the Phase 3 report's numbers.
"""

from __future__ import annotations

import asyncio
from datetime import date

from momentum25.application.use_cases.research.swing_target_backtest import (
    SwingTargetBacktestUseCase,
)
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.repositories import (
    SqlOHLCVRepository,
    SqlScreeningRunRepository,
    SqlSecurityRepository,
    SqlStrategyRepository,
)
from momentum25.infrastructure.pipelines.indicator_pipeline import IndicatorPipelineImpl


def _print_report(label: str, report: object) -> None:
    print(f"\n=== {label} ===")
    for field in (
        "total_trades", "target_hits", "stop_hits", "time_exits", "insufficient_data",
        "hit_rate", "avg_r_multiple",
        "avg_max_adverse_excursion_r", "worst_max_adverse_excursion_r",
    ):
        print(f"  {field}: {getattr(report, field)}")


async def main() -> None:
    """Run the full-history and hold-out backtests and print both reports."""
    async with get_database().session() as session:
        use_case = SwingTargetBacktestUseCase(
            screening_run_repo=SqlScreeningRunRepository(session),
            security_repo=SqlSecurityRepository(session),
            ohlcv_repo=SqlOHLCVRepository(session),
            strategy_repo=SqlStrategyRepository(session),
            indicator_pipeline=IndicatorPipelineImpl(session),
            max_holding_days=20,
        )

        full = await use_case.execute(
            "minervini_trend_template", start_date=date(2000, 1, 1), end_date=date(2026, 12, 31)
        )
        _print_report("Full history (2019-10-01 .. latest)", full)

        holdout_start = date(2025, 1, 1)
        holdout = await use_case.execute(
            "minervini_trend_template", start_date=holdout_start, end_date=date(2026, 12, 31)
        )
        _print_report(f"Hold-out fold ({holdout_start} onward)", holdout)

        pre_holdout = await use_case.execute(
            "minervini_trend_template", start_date=date(2000, 1, 1), end_date=date(2024, 12, 31)
        )
        _print_report("Pre-hold-out (in-sample period, for comparison)", pre_holdout)


if __name__ == "__main__":
    asyncio.run(main())
