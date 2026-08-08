"""Swing target/stop-loss backtest (Phase 3.3).

Walk-forward evaluation of :func:`compute_swing_target_plan` against real
signals: every security that actually passed hard filters (``rank is not
None``) in a strategy's completed screening runs within a date range, with
its indicators recomputed as-of the signal date (no lookahead -- the
indicator pipeline only ever reads bars up to and including ``run_date``,
the same guarantee every other historical-replay path in this codebase
relies on).

Read-only over already-completed runs, matching
``HistoricalValidationUseCase``'s default non-invasive behaviour: this never
triggers new screening. If a strategy has no completed runs in the requested
window, the report says so explicitly (``signals_examined == 0``) rather
than silently returning an empty-but-plausible-looking report.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

from momentum25.domain.research.swing_targets import (
    DEFAULT_ATR_STOP_MULTIPLE,
    DEFAULT_ATR_TARGET_MULTIPLE,
    SwingTargetBacktestReport,
    aggregate_trade_results,
    compute_swing_target_plan,
    simulate_trade,
)
from momentum25.domain.value_objects.indicators import IndicatorSet
from momentum25.infrastructure.logging.setup import get_logger

_logger = get_logger("swing_target_backtest")

_DEFAULT_MAX_HOLDING_DAYS = 20

# A regime/setup-strength filter (Phase 3b.2): given the indicators computed
# at signal time, decide whether this signal is even eligible for the
# backtest. `None` means "no filter, include every passing signal" (Phase 3
# behaviour, preserved as the default).
RegimeFilter = Callable[[IndicatorSet], bool]


class SwingTargetBacktestUseCase:
    """Backtest the swing target/stop plan against a strategy's historical signals."""

    def __init__(
        self,
        screening_run_repo: Any,
        security_repo: Any,
        ohlcv_repo: Any,
        strategy_repo: Any,
        indicator_pipeline: Any,
        max_holding_days: int = _DEFAULT_MAX_HOLDING_DAYS,
        atr_stop_multiple: Decimal = DEFAULT_ATR_STOP_MULTIPLE,
        atr_target_multiple: Decimal = DEFAULT_ATR_TARGET_MULTIPLE,
        regime_filter: RegimeFilter | None = None,
        min_rr_ratio: Decimal | None = None,
    ) -> None:
        """Wire the use case with its collaborators.

        ``atr_stop_multiple``/``atr_target_multiple`` and ``regime_filter``
        exist to let Phase 3b research alternative plan configurations and
        conditioning rules without duplicating this use case (3b.1/3b.2).
        """
        self._screening_run_repo = screening_run_repo
        self._security_repo = security_repo
        self._ohlcv_repo = ohlcv_repo
        self._strategy_repo = strategy_repo
        self._indicator_pipeline = indicator_pipeline
        self._max_holding_days = max_holding_days
        self._atr_stop_multiple = atr_stop_multiple
        self._atr_target_multiple = atr_target_multiple
        self._regime_filter = regime_filter
        self._min_rr_ratio = min_rr_ratio

    async def execute(
        self, strategy_name: str, start_date: date, end_date: date
    ) -> SwingTargetBacktestReport:
        """Backtest every passing signal for *strategy_name* within ``[start_date, end_date]``.

        Returns:
            A :class:`SwingTargetBacktestReport` with ``total_trades == 0``
            (all rates ``None``) if the strategy has no completed runs, or no
            passing signals, in the requested window -- this is a real,
            reportable outcome, not an error.
        """
        strategy = await self._strategy_repo.get_active(strategy_name)
        if strategy is None:
            _logger.warning("swing_backtest_strategy_not_found", strategy=strategy_name)
            return aggregate_trade_results([])

        runs, _ = await self._screening_run_repo.list_runs(
            status="COMPLETED",
            limit=10_000,
            offset=0,
            exclude_historical=False,
            exclude_research=True,
            strategy_id=strategy.id,
        )
        runs_in_range = [r for r in runs if start_date <= r.run_date <= end_date]

        securities = await self._security_repo.list_all()
        symbol_by_id = {s.id: str(s.symbol) for s in securities}

        trade_results = []
        for run in runs_in_range:
            rankings, _ = await self._screening_run_repo.get_rankings(
                run.id, limit=10_000, offset=0
            )
            for ranking in rankings:
                if ranking.rank is None:
                    continue  # did not pass hard filters -- not a real signal
                symbol = symbol_by_id.get(ranking.security_id)
                result = await self._simulate_one_signal(
                    ranking.security_id, symbol, run.run_date, strategy
                )
                if result is not None:
                    trade_results.append(result)

        report = aggregate_trade_results(trade_results)
        _logger.info(
            "swing_backtest_completed",
            strategy=strategy_name,
            runs_examined=len(runs_in_range),
            total_trades=report.total_trades,
            hit_rate=str(report.hit_rate) if report.hit_rate is not None else None,
            avg_r_multiple=(
                str(report.avg_r_multiple) if report.avg_r_multiple is not None else None
            ),
        )
        return report

    async def _simulate_one_signal(
        self, security_id: int, symbol: str | None, run_date: date, strategy: Any
    ) -> Any:
        """Build a plan for one passing signal and simulate it forward, or ``None`` if unusable."""
        if symbol is None:
            return None

        indicators = await self._indicator_pipeline.compute(
            symbol, run_date, strategy.config.indicators
        )
        if indicators.sma200 is None:
            return None  # insufficient history at signal time
        if self._regime_filter is not None and not self._regime_filter(indicators):
            return None  # signal excluded by this configuration's regime filter (3b.2)

        series = await self._ohlcv_repo.get_series(security_id, lookback_days=1, as_of=run_date)
        if series.latest is None:
            return None
        entry = series.latest.close

        plan = compute_swing_target_plan(
            entry,
            indicators.atr14,
            indicators.swing_resistance,
            atr_stop_multiple=self._atr_stop_multiple,
            atr_target_multiple=self._atr_target_multiple,
        )
        if plan is None:
            return None
        if self._min_rr_ratio is not None and plan.rr_ratio < self._min_rr_ratio:
            return None  # signal-time RR gate (3b.1) -- decided before entry, not after the fact

        forward_bars = await self._ohlcv_repo.get_bars_after(
            security_id, after_date=run_date, limit=self._max_holding_days
        )
        return simulate_trade(plan, forward_bars, self._max_holding_days)
