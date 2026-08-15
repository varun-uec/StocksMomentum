"""Watchlist use cases (Phase 6.9)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from momentum25.application.dto.watchlist import WatchlistDetailResponseDTO, WatchlistItemDTO
from momentum25.application.services.rs_ratings import (
    RsRatingCache,
    resolve_universe_rs_ratings,
)
from momentum25.application.use_cases.screening_orchestrator import build_evaluation_context
from momentum25.domain.entities.security import Security
from momentum25.domain.errors import NotFoundError, StrategyNotFoundError
from momentum25.domain.ports.repositories import SecurityRepository, WatchlistRepository
from momentum25.domain.value_objects.results import RuleResult


async def _resolve_security_id(securities: SecurityRepository, symbol: str) -> int:
    """Return the security id for ``symbol``, or raise :class:`NotFoundError`."""
    security = await securities.get_by_symbol(symbol)
    if security is None or security.id is None:
        raise NotFoundError(f"Security not found: {symbol}")
    return security.id


class GetWatchlist:
    """Return the watchlisted symbols."""

    def __init__(self, watchlist: WatchlistRepository) -> None:
        """Wire the use case with its collaborators."""
        self._watchlist = watchlist

    async def execute(self) -> list[str]:
        """Return the watchlisted symbols, oldest addition first."""
        return await self._watchlist.list_symbols()


class AddToWatchlist:
    """Add a symbol to the watchlist."""

    def __init__(self, securities: SecurityRepository, watchlist: WatchlistRepository) -> None:
        """Wire the use case with its collaborators."""
        self._securities = securities
        self._watchlist = watchlist

    async def execute(self, symbol: str) -> None:
        """Add ``symbol``; idempotent, raises if the symbol is unknown."""
        await self._watchlist.add(await _resolve_security_id(self._securities, symbol))


class RemoveFromWatchlist:
    """Remove a symbol from the watchlist."""

    def __init__(self, securities: SecurityRepository, watchlist: WatchlistRepository) -> None:
        """Wire the use case with its collaborators."""
        self._securities = securities
        self._watchlist = watchlist

    async def execute(self, symbol: str) -> None:
        """Remove ``symbol``; idempotent, raises if the symbol is unknown."""
        await self._watchlist.remove(await _resolve_security_id(self._securities, symbol))


def _require_id(security: Security) -> int:
    """Return a security's id, which callers have already established exists."""
    if security.id is None:
        raise NotFoundError(f"Security has no id: {security.symbol}")
    return security.id


def _raw_value(rule_results: list[RuleResult], rule_id: str) -> Decimal | None:
    return next((r.raw_value for r in rule_results if r.rule_id == rule_id), None)


class GetWatchlistDetail:
    """Return the watchlist enriched with momentum/rank/RS for every symbol.

    Symbols in the strategy's latest completed run read straight from
    persisted results. Symbols outside it -- skipped or newly admitted since
    that run -- are evaluated live through the same
    :func:`build_evaluation_context` + ``StrategyEngine.score_security`` pair
    the orchestrator and the single-symbol ``/live`` endpoint use, so all
    three paths agree by construction. The expensive part, universe-relative
    RS ratings, is computed once per request (not once per symbol) and
    cached by trading date so repeat loads are fast.
    """

    def __init__(
        self,
        watchlist: WatchlistRepository,
        securities: SecurityRepository,
        screening_run_repo: Any,
        strategies: Any,
        ohlcv_repo: Any,
        indicator_pipeline: Any,
        strategy_engine: Any,
        rs_rating_cache: RsRatingCache | None = None,
    ) -> None:
        """Wire the use case with its collaborators."""
        self._watchlist = watchlist
        self._securities = securities
        self._screening_run_repo = screening_run_repo
        self._strategies = strategies
        self._ohlcv_repo = ohlcv_repo
        self._indicator_pipeline = indicator_pipeline
        self._strategy_engine = strategy_engine
        self._rs_rating_cache = rs_rating_cache

    async def execute(self, strategy_name: str) -> WatchlistDetailResponseDTO:
        """Return every watchlisted symbol's momentum snapshot for *strategy_name*."""
        symbols = await self._watchlist.list_symbols()
        if not symbols:
            return WatchlistDetailResponseDTO(strategy=strategy_name, run_id=None, items=[])

        strategy = await self._strategies.get_active(strategy_name)
        if strategy is None or strategy.id is None:
            raise StrategyNotFoundError(f"Strategy not found: {strategy_name}")

        run = await self._screening_run_repo.latest_completed(strategy.id)

        securities: list[Security] = []
        for symbol in symbols:
            security = await self._securities.get_by_symbol(symbol)
            if security is not None and security.id is not None:
                securities.append(security)

        prev_ranks: dict[int, int] = {}
        if run is not None and run.id is not None:
            prev_ranks = await self._screening_run_repo.get_previous_run_ranks(
                strategy.id, run.id, run.run_date
            )

        in_run: list[Security] = []
        out_of_run: list[Security] = []
        for security in securities:
            result = None
            if run is not None and run.id is not None:
                result = await self._screening_run_repo.get_screening_result(run.id, security.id)
            (in_run if result is not None else out_of_run).append(security)

        items: list[WatchlistItemDTO] = []
        for security in in_run:
            items.append(await self._build_in_run_item(security, run, prev_ranks))

        if out_of_run:
            as_of = run.run_date if run is not None else date.today()
            rs_ratings = await self._universe_rs_ratings(strategy, as_of)
            for security in out_of_run:
                items.append(await self._build_live_item(security, strategy, as_of, rs_ratings))

        order = {symbol: i for i, symbol in enumerate(symbols)}
        items.sort(key=lambda item: order.get(item.symbol, len(order)))

        return WatchlistDetailResponseDTO(
            strategy=strategy_name, run_id=run.id if run else None, items=items
        )

    async def _build_in_run_item(
        self, security: Security, run: Any, prev_ranks: dict[int, int]
    ) -> WatchlistItemDTO:
        # ``execute`` only collects securities with an id, so this never raises.
        security_id = _require_id(security)
        result = await self._screening_run_repo.get_screening_result(run.id, security_id)
        rule_results = await self._screening_run_repo.get_rule_results(run.id, security_id)
        rs_rating = _raw_value(rule_results, "tt_rs_rating_min")
        pct_below_high = _raw_value(rule_results, "tt_near_52w_high")
        rank_change = None
        if result.rank is not None:
            prev = prev_ranks.get(security_id)
            if prev is not None:
                rank_change = prev - result.rank
        close, change_pct = await self._last_close(security_id)
        return WatchlistItemDTO(
            symbol=str(security.symbol),
            in_latest_run=True,
            momentum_score=result.momentum_score,
            buy_setup_score=result.buy_setup_score,
            rank=result.rank,
            rank_change=rank_change,
            rs_rating=int(rs_rating) if rs_rating is not None else None,
            pct_below_high_52w=pct_below_high,
            close=close,
            change_pct=change_pct,
        )

    async def _build_live_item(
        self, security: Security, strategy: Any, as_of: date, rs_ratings: dict[str, int]
    ) -> WatchlistItemDTO:
        symbol = str(security.symbol)
        close, change_pct = await self._last_close(_require_id(security))
        indicators = await self._indicator_pipeline.compute(
            symbol, as_of, strategy.config.indicators
        )
        if indicators.sma200 is None:
            return WatchlistItemDTO(
                symbol=symbol, in_latest_run=False, close=close, change_pct=change_pct
            )

        rating = rs_ratings.get(symbol)
        if rating is not None:
            object.__setattr__(indicators, "rs_rating", rating)

        ctx = await build_evaluation_context(security, indicators, self._ohlcv_repo, as_of)
        score = self._strategy_engine.score_security(ctx, strategy)

        return WatchlistItemDTO(
            symbol=symbol,
            in_latest_run=False,
            momentum_score=score.momentum_score,
            buy_setup_score=score.buy_setup_score,
            rank=None,
            rank_change=None,
            rs_rating=rating,
            pct_below_high_52w=indicators.pct_below_high_52w,
            close=close,
            change_pct=change_pct,
        )

    async def _universe_rs_ratings(self, strategy: Any, as_of: date) -> dict[str, int]:
        return await resolve_universe_rs_ratings(
            self._securities, self._ohlcv_repo, strategy, as_of, self._rs_rating_cache
        )

    async def _last_close(self, security_id: int) -> tuple[Decimal | None, Decimal | None]:
        series = await self._ohlcv_repo.get_series(security_id, lookback_days=5, as_of=date.today())
        bars = series.bars if series else ()
        if not bars:
            return None, None
        close = bars[-1].close
        if len(bars) < 2:
            return close, None
        prev = bars[-2].close
        change_pct = ((close - prev) / prev * 100) if prev else None
        return close, change_pct
