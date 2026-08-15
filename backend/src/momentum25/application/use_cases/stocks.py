"""Stock explainability and history use cases."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date
from typing import Any

from momentum25.application.dto.market_data import (
    IndicatorBarDTO,
    SecurityIndicatorSeriesDTO,
)
from momentum25.application.dto.stocks import ScorePointDTO, StockHistoryDTO
from momentum25.application.services.rs_ratings import (
    RsRatingCache,
    resolve_universe_rs_ratings,
)
from momentum25.application.use_cases.rankings import bind_builder_to_run, qualified_count
from momentum25.application.use_cases.screening_orchestrator import build_evaluation_context
from momentum25.domain.analytics.market_context import (
    RS_PERIODS,
    RelativeStrengthPoint,
    relative_strength_vs_index,
)
from momentum25.domain.entities.market_data import OHLCVBar
from momentum25.domain.errors import NotFoundError, StrategyNotFoundError
from momentum25.domain.ports.repositories import (
    BenchmarkIndexRepository,
    OHLCVRepository,
    ScreeningRunRepository,
    SecurityRepository,
    StrategyRepository,
)
from momentum25.domain.research.stop_loss import (
    DEFAULT_CHANDELIER_LOOKBACK,
    StopLossSuggestion,
    suggest_chandelier_stop,
    suggest_stop_loss,
)
from momentum25.domain.scoring.explainability import ExplainabilityBuilderImpl, StockExplanation
from momentum25.domain.value_objects.indicators import IndicatorSet
from momentum25.infrastructure.logging.setup import get_logger

_DEFAULT_STRATEGY = "minervini_trend_template"
_RS_INDETERMINATE_RULE_ID = "tt_rs_rating_min"

_logger = get_logger("live_stock_analysis")


def _indicator_snapshot(indicators: IndicatorSet) -> dict[str, Any]:
    """Render an :class:`IndicatorSet` as a JSON-friendly dict (Decimals as strings).

    Exposes every computed indicator -- including ADX/+DI/-DI, MACD, and swing
    pivot support/resistance (Phase 2.1/2.2/2.3) -- as data on the live lookup
    response, rather than only as internal inputs consumed by rule evaluation.
    """
    from dataclasses import fields as _dataclass_fields

    snapshot: dict[str, Any] = {}
    for f in _dataclass_fields(indicators):
        if f.name == "as_of":
            continue
        value = getattr(indicators, f.name)
        snapshot[f.name] = str(value) if value is not None else None
    return snapshot


class GetStockExplanation:
    """Return the full explainability payload for a stock."""

    def __init__(
        self,
        securities: SecurityRepository,
        screening_run_repo: ScreeningRunRepository,
        explainability_builder: ExplainabilityBuilderImpl,
        strategies: StrategyRepository | None = None,
    ) -> None:
        """Wire the use case with security, run, and explainability collaborators."""
        self._securities = securities
        self._screening_run_repo = screening_run_repo
        self._explainability_builder = explainability_builder
        self._strategies = strategies

    async def execute(
        self,
        symbol: str,
        run_id: int | None,
        strategy_name: str = _DEFAULT_STRATEGY,
    ) -> StockExplanation:
        """Return a stock explanation from ``run_id``.

        If ``run_id`` is omitted, uses the latest completed run for
        ``strategy_name`` (e.g. a Momentum Horizon) instead.
        """
        security = await self._securities.get_by_symbol(symbol)
        if security is None or security.id is None:
            raise NotFoundError(f"Security not found: {symbol}")

        if run_id is None:
            if self._strategies is None:
                raise NotFoundError("No strategy repository configured.")
            strategy = await self._strategies.get_active(strategy_name)
            if strategy is None or strategy.id is None:
                raise StrategyNotFoundError(f"Strategy not found: {strategy_name}")
            run = await self._screening_run_repo.latest_completed(strategy.id)
            if run is None or run.id is None:
                raise NotFoundError(f"No completed runs found for strategy {strategy_name}.")
            run_id = run.id
        else:
            run = await self._screening_run_repo.get(run_id)

        rule_results = await self._screening_run_repo.get_rule_results(
            run_id, security.id
        )
        if not rule_results:
            raise NotFoundError(
                f"No screening results for {symbol} in run {run_id}."
            )

        ranking = await self._screening_run_repo.get_screening_result(run_id, security.id)
        builder = await bind_builder_to_run(
            self._explainability_builder, self._strategies, run
        )
        explanation = builder.build_historical_explanation(
            run_id, security.id, rule_results, ranking, qualified_count(run)
        )
        return StockExplanation(
            symbol=str(security.symbol),
            security_id=explanation.security_id,
            overall_passed=explanation.overall_passed,
            momentum_score=explanation.momentum_score,
            buy_setup_score=explanation.buy_setup_score,
            composite_score=explanation.composite_score,
            rank=explanation.rank,
            percentile=explanation.percentile,
            rule_explanations=explanation.rule_explanations,
            engine_explanations=explanation.engine_explanations,
            hard_filter_failures=explanation.hard_filter_failures,
            overall_rationale=explanation.overall_rationale,
        )


class GetStockHistory:
    """Return a stock's score/rank history across runs."""

    def __init__(
        self,
        securities: SecurityRepository,
        screening_run_repo: ScreeningRunRepository,
        strategies: StrategyRepository,
    ) -> None:
        """Wire the use case with security, run, and strategy collaborators."""
        self._securities = securities
        self._screening_run_repo = screening_run_repo
        self._strategies = strategies

    async def execute(self, symbol: str, strategy_name: str, limit: int) -> StockHistoryDTO:
        """Return history points for a symbol, scoped to one strategy (e.g. a Momentum Horizon).

        One query, not one per run: the previous implementation listed every
        completed run and pulled up to 10,000 rankings from each just to find a
        single security.
        """
        security = await self._securities.get_by_symbol(symbol)
        if security is None or security.id is None:
            raise NotFoundError(f"Security not found: {symbol}")

        strategy = await self._strategies.get_active(strategy_name)
        if strategy is None or strategy.id is None:
            raise StrategyNotFoundError(f"Strategy not found: {strategy_name}")

        history = await self._screening_run_repo.score_history(
            strategy_id=strategy.id, security_id=security.id, limit=limit
        )
        return StockHistoryDTO(
            symbol=symbol,
            score_history=[
                ScorePointDTO(
                    run_date=point.run_date,
                    security_id=security.id,
                    rank=point.rank,
                    momentum_score=point.momentum_score,
                    buy_setup_score=point.buy_setup_score,
                )
                for point in history
            ],
        )


class GetIndicatorSeries:
    """Return a symbol's per-bar indicator series for the chart sub-panes (Phase 9).

    A thin, purely additive read over the same pipeline the live snapshot uses
    (:meth:`IndicatorPipelineImpl.compute_series` reuses the exact ``_*_series``
    functions whose final elements produce the snapshot's latest values), so the
    series' last bar always agrees with ``/stocks/{symbol}/live``. No new
    indicator math exists here; nothing here is scored or interpreted.
    """

    def __init__(
        self,
        securities: SecurityRepository,
        strategies: StrategyRepository,
        indicator_pipeline: Any,
    ) -> None:
        """Wire the use case with its collaborators."""
        self._securities = securities
        self._strategies = strategies
        self._indicator_pipeline = indicator_pipeline

    async def execute(
        self, symbol: str, strategy_name: str = _DEFAULT_STRATEGY
    ) -> SecurityIndicatorSeriesDTO:
        """Return the indicator series for *symbol* under *strategy_name*."""
        security = await self._securities.get_by_symbol(symbol)
        if security is None or security.id is None:
            raise NotFoundError(f"Security not found: {symbol}")

        strategy = await self._strategies.get_active(strategy_name)
        if strategy is None or strategy.id is None:
            raise StrategyNotFoundError(f"Strategy not found: {strategy_name}")

        series = await self._indicator_pipeline.compute_series(
            symbol, date.today(), strategy.config.indicators
        )

        # Strict zipping: compute_series guarantees all arrays equal `dates`'
        # length, so a mismatch is a pipeline bug and must surface loudly.
        bars = [
            IndicatorBarDTO(
                date=d,
                rsi14=rsi14,
                atr14=atr14,
                adx14=adx14,
                macd_line=macd_line,
                macd_signal=macd_signal,
                macd_histogram=macd_histogram,
            )
            for d, rsi14, atr14, adx14, macd_line, macd_signal, macd_histogram in zip(
                series.dates,
                series.rsi14,
                series.atr14,
                series.adx14,
                series.macd_line,
                series.macd_signal,
                series.macd_histogram,
                strict=True,
            )
        ]
        return SecurityIndicatorSeriesDTO(symbol=str(security.symbol), bars=bars)


class RefreshGate:
    """No-op refresh gate: always allows a refresh, records nothing.

    A live lookup calling out to NSE on every request would make naive
    per-request scraping trivially detectable and blockable (Phase 1.3).
    The default here has no cooldown; ``interface/api/dependencies.py``
    substitutes a Redis-backed gate when Redis is available, and this
    class is that fallback -- so a Redis outage degrades to "no cooldown",
    never a 500.
    """

    async def should_refresh(self, symbol: str) -> bool:
        """Return whether a refresh is currently allowed for *symbol*."""
        return True

    async def mark_refreshed(self, symbol: str) -> None:
        """Record that *symbol* was just refreshed."""


@dataclass(frozen=True, slots=True)
class LiveStockAnalysis:
    """Result of an on-demand, freshly-evaluated single-symbol lookup."""

    symbol: str
    verdict: str  # "PASSED" | "FAILED" | "INDETERMINATE" | "INSUFFICIENT_DATA"
    data_as_of: date
    refreshed: bool
    bars_fetched: int
    data_sufficient: bool
    explanation: StockExplanation | None = None
    indeterminate_rules: tuple[str, ...] = field(default_factory=tuple)
    rs_basis: dict[str, Any] = field(default_factory=dict)
    indicators: dict[str, Any] = field(default_factory=dict)
    suggested_stop: StopLossSuggestion | None = None
    # Phase 6.5 — trailing (chandelier) variant of ``suggested_stop``. Both are
    # downside caps; neither implies a target or a reward.
    trailing_stop: StopLossSuggestion | None = None
    # Phase 6.2 — stock return minus benchmark-index return over 1/3/6/12 months.
    # Empty when the configured benchmark index has no ingested history: an
    # unmeasured excess return is reported as absent, never as zero.
    relative_strength_vs_index: tuple[RelativeStrengthPoint, ...] = field(default_factory=tuple)
    benchmark_index: str | None = None


class GetLiveStockAnalysis:
    """Evaluate one symbol on demand through the real strategy engine.

    Reuses the same :func:`build_evaluation_context` and :class:`StrategyEngine`
    as the daily orchestrator (Phase 1.1) rather than a second hand-rolled
    evaluation -- the bug that motivated deleting
    ``MarketSyncService._evaluate_trend_template``.
    """

    def __init__(
        self,
        securities: SecurityRepository,
        ohlcv_repo: OHLCVRepository,
        strategies: StrategyRepository,
        indicator_pipeline: Any,
        strategy_engine: Any,
        explainability_builder: ExplainabilityBuilderImpl,
        nse_client: Any,
        refresh_gate: RefreshGate | None = None,
        benchmark_repo: BenchmarkIndexRepository | None = None,
        rs_rating_cache: RsRatingCache | None = None,
    ) -> None:
        """Wire the use case with its collaborators.

        ``benchmark_repo`` is optional: without it the index-relative strength
        block (Phase 6.2) is simply absent from the response, which is the
        correct degradation -- the alternative would be reporting an excess
        return computed against a benchmark that was never loaded.

        ``rs_rating_cache`` is optional in the same way: without it every
        request recomputes the universe RS table, which is correct but slow.
        """
        self._securities = securities
        self._ohlcv_repo = ohlcv_repo
        self._strategies = strategies
        self._indicator_pipeline = indicator_pipeline
        self._strategy_engine = strategy_engine
        self._explainability_builder = explainability_builder
        self._nse_client = nse_client
        self._refresh_gate = refresh_gate or RefreshGate()
        self._benchmark_repo = benchmark_repo
        self._rs_rating_cache = rs_rating_cache

    async def execute(
        self,
        symbol: str,
        strategy_name: str = _DEFAULT_STRATEGY,
        refresh: bool = False,
        as_of: date | None = None,
    ) -> LiveStockAnalysis:
        """Fetch (if requested), compute, and evaluate one symbol on demand."""
        security = await self._securities.get_by_symbol(symbol)
        if security is None or security.id is None:
            raise NotFoundError(f"Security not found: {symbol}")

        strategy = await self._strategies.get_active(strategy_name)
        if strategy is None or strategy.id is None:
            raise StrategyNotFoundError(f"Strategy not found: {strategy_name}")

        reference_date = as_of or date.today()
        refreshed = False
        bars_fetched = 0

        if refresh and await self._refresh_gate.should_refresh(symbol):
            bars_fetched = await self._refresh_bars(symbol, security.id, reference_date)
            await self._refresh_gate.mark_refreshed(symbol)
            refreshed = bars_fetched > 0

        indicators = await self._indicator_pipeline.compute(
            symbol, reference_date, strategy.config.indicators
        )
        if indicators.sma200 is None:
            _logger.info("live_lookup_insufficient_data", symbol=symbol)
            return LiveStockAnalysis(
                symbol=str(security.symbol),
                verdict="INSUFFICIENT_DATA",
                data_as_of=reference_date,
                refreshed=refreshed,
                bars_fetched=bars_fetched,
                data_sufficient=False,
                indicators=_indicator_snapshot(indicators),
            )

        rs_rating, rs_basis = await self._resolve_rs_rating(symbol, strategy, reference_date)
        if rs_rating is not None:
            object.__setattr__(indicators, "rs_rating", rs_rating)

        ctx = await build_evaluation_context(security, indicators, self._ohlcv_repo, reference_date)
        score = self._strategy_engine.score_security(ctx, strategy)

        suggested_stop = suggest_stop_loss(
            entry=ctx.series.bars[-1].close,
            atr14=indicators.atr14,
            swing_support=indicators.swing_support,
        )
        recent_highs = [b.high for b in ctx.series.bars[-DEFAULT_CHANDELIER_LOOKBACK:]]
        trailing_stop = suggest_chandelier_stop(
            highest_high=max(recent_highs) if recent_highs else None,
            atr14=indicators.atr14,
        )

        rs_vs_index, benchmark_index = await self._relative_strength_vs_index(
            security.id, strategy.config.benchmark_index, reference_date
        )

        all_rules = [rr for er in score.engine_results for rr in er.rule_results]
        explanation = self._explainability_builder.for_strategy(
            strategy.config
        ).build_explanation(score, all_rules)

        indeterminate_rules = tuple(
            rr.rule_id
            for rr in all_rules
            if rr.rule_id == _RS_INDETERMINATE_RULE_ID and rr.raw_value is None
        )

        if explanation.overall_passed:
            verdict = "PASSED"
        elif indeterminate_rules and set(explanation.hard_filter_failures) <= set(
            indeterminate_rules
        ):
            verdict = "INDETERMINATE"
        else:
            verdict = "FAILED"

        # RuleResult stays binary (Phase 1.2 decision -- see module docstring
        # on GetLiveStockAnalysis): the domain engine has no concept of
        # "insufficient data" distinct from "failed", so an indeterminate rule
        # is reported as `passed=False` internally. The application boundary
        # is where "we couldn't measure this" is distinguished from "this
        # failed" -- surfaced via `verdict`/`indeterminate_rules`, and by
        # excluding indeterminate rules from the hard-filter-failure list so
        # a client doesn't render "RS rating failed" for a rating that was
        # never computed.
        visible_hard_failures = tuple(
            r for r in explanation.hard_filter_failures if r not in indeterminate_rules
        )
        explanation = replace(
            explanation, symbol=str(security.symbol), hard_filter_failures=visible_hard_failures
        )

        return LiveStockAnalysis(
            symbol=str(security.symbol),
            verdict=verdict,
            data_as_of=reference_date,
            refreshed=refreshed,
            bars_fetched=bars_fetched,
            data_sufficient=True,
            explanation=explanation,
            indeterminate_rules=indeterminate_rules,
            rs_basis=rs_basis,
            indicators=_indicator_snapshot(indicators),
            suggested_stop=suggested_stop,
            trailing_stop=trailing_stop,
            relative_strength_vs_index=rs_vs_index,
            benchmark_index=benchmark_index,
        )

    async def _relative_strength_vs_index(
        self, security_id: int, benchmark_index: str | None, as_of: date
    ) -> tuple[tuple[RelativeStrengthPoint, ...], str | None]:
        """Return the stock's excess return over the strategy's benchmark index.

        Returns an empty tuple when no benchmark is configured, no benchmark
        repository is wired, or the index has no ingested closes. Only
        ``NIFTY500`` has been backfilled into ``benchmark_index_daily`` -- see
        ``application/use_cases/validation.py`` for why a missing index must not
        be silently replaced with a flat 0% series.
        """
        if self._benchmark_repo is None or not benchmark_index:
            return (), benchmark_index

        index_closes = await self._benchmark_repo.get_close_series(benchmark_index)
        if not index_closes:
            _logger.info("rs_vs_index_unavailable", index=benchmark_index)
            return (), benchmark_index

        # One extra session of headroom beyond the longest lookback so the 12m
        # window survives any dates the stock and index do not share.
        lookback = max(sessions for _, sessions in RS_PERIODS) + 50
        series = await self._ohlcv_repo.get_series(
            security_id, lookback_days=lookback, as_of=as_of
        )
        stock_closes = {bar.date: bar.close for bar in series.bars}
        return (
            relative_strength_vs_index(stock_closes, index_closes),
            benchmark_index,
        )

    async def _refresh_bars(self, symbol: str, security_id: int, reference_date: date) -> int:
        """Fetch fresh bars from NSE and persist them. Returns bars upserted."""
        from datetime import timedelta

        start_date = reference_date - timedelta(days=500)
        try:
            raw_bars = await self._nse_client.fetch_historical_bars(
                symbol=symbol, start_date=start_date, end_date=reference_date
            )
        except Exception as exc:
            _logger.warning("live_refresh_fetch_failed", symbol=symbol, error=str(exc))
            return 0

        if not raw_bars:
            return 0

        bars = [
            OHLCVBar(
                date=b.date,
                open=b.open,
                high=b.high,
                low=b.low,
                close=b.close,
                volume=b.volume,
                prev_close=b.prev_close,
                turnover_value=b.turnover_value,
            )
            for b in raw_bars
        ]
        upserted = await self._ohlcv_repo.upsert_bars(security_id, bars)
        commit = getattr(self._ohlcv_repo, "_session", None)
        if commit is not None:
            await commit.commit()
        return upserted

    async def _resolve_rs_rating(
        self, symbol: str, strategy: Any, as_of: date
    ) -> tuple[int | None, dict[str, Any]]:
        """Rank *symbol* against the persisted active universe as of *as_of*.

        A single symbol has no universe to percentile against on its own
        (Phase 1.2), so RS is computed the same way the daily orchestrator
        computes it: against every other active, persisted security. That walk
        costs ~8 s over a ~2,000-security universe, and it produces the same
        table for every symbol looked up on the same trading date, so the
        result is shared through the same cache ``/watchlist/detail`` uses.
        """
        ratings = await resolve_universe_rs_ratings(
            self._securities, self._ohlcv_repo, strategy, as_of, self._rs_rating_cache
        )
        rs_basis = {
            "universe_size": len(ratings),
            "as_of": as_of.isoformat(),
            "symbol_in_universe": symbol in ratings,
        }
        return ratings.get(symbol), rs_basis
