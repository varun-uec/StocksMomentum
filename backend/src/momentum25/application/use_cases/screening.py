"""ExecuteScreening — run the full end-to-end screening pipeline.

Fetches EOD market data via the :class:`MarketDataProvider` port (BhavcopyProvider
per ADR-003), populates the database, then executes the full screening pipeline
through :class:`ScreeningOrchestrator`:

    Market Data → Indicator Pipeline → Strategy Engine → Rule Engine →
    Scoring Engine → Ranking Engine → Persistence

This is the integration use case that wires the complete hexagon together
for the vertical slice.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, cast

from structlog import get_logger

from momentum25.domain.entities.market_data import OHLCVBar
from momentum25.domain.entities.security import Security
from momentum25.domain.entities.strategy import Strategy
from momentum25.domain.value_objects.types import Symbol

_logger = get_logger("execute_screening")

# Ensure enough history for 200 SMA + 22-day slope calculation
_MIN_HISTORY_CALENDAR_DAYS = 500


class ExecuteScreening:
    """Fetch EOD data and run the full screening pipeline.

    The use case:
        1. Resolves the strategy from the database.
        2. Fetches EOD bars for the lookback window via the MarketDataProvider port.
        3. Derives the symbol universe from the latest EOD file and upserts securities.
        4. Persists historical OHLCV bars.
        5. Delegates to :class:`ScreeningOrchestrator` for the rest of the pipeline.

    Attributes:
        market_data_provider: The MarketDataProvider port (e.g. BhavcopyProvider).
        security_repo: Repository for securities.
        ohlcv_repo: Repository for OHLCV bar persistence.
        screening_run_repo: Repository for screening runs and results.
        indicator_pipeline: Technical indicator computation pipeline.
        strategy_engine: The strategy orchestrator (engines → scoring → ranking).
    """

    def __init__(
        self,
        market_data_provider: Any,
        security_repo: Any,
        ohlcv_repo: Any,
        screening_run_repo: Any,
        indicator_pipeline: Any,
        strategy_engine: Any,
    ) -> None:
        """Wire the use case with its collaborators."""
        self._market_data_provider = market_data_provider
        self._security_repo = security_repo
        self._ohlcv_repo = ohlcv_repo
        self._screening_run_repo = screening_run_repo
        self._indicator_pipeline = indicator_pipeline
        self._strategy_engine = strategy_engine

    async def execute(
        self,
        strategy_name: str,
        target_symbols: list[str] | None = None,
        force: bool = False,  # noqa: ARG002 – reserved for future idempotency
    ) -> int:
        """Execute the full end-to-end screening pipeline.

        Args:
            strategy_name: Name of the strategy to run (loaded from DB).
            target_symbols: Optional list of symbols to screen. If ``None``,
                the universe is derived from the latest EOD file.
            force: Reserved for future idempotency check.

        Returns:
            The id of the created screening run.

        Raises:
            :class:`RuntimeError` if the strategy is not found.
        """
        _logger.info(
            "execute_screening_started",
            strategy=strategy_name,
            target_symbols=target_symbols,
        )

        # 1. Resolve the strategy
        strategy = await self._resolve_strategy(strategy_name)

        reference_date = date.today()
        start_date = reference_date - timedelta(days=_MIN_HISTORY_CALENDAR_DAYS)

        # 2. Fetch EOD bars for the lookback window via the MarketDataProvider port
        all_bars = await self._fetch_eod_range(start_date, reference_date)

        if not all_bars:
            raise ValueError("No market data available for screening")

        # 3. Resolve the symbol universe
        if target_symbols:
            symbols = target_symbols
        else:
            # Derive universe from the latest available trading date
            latest_bars = [b for b in all_bars if b.date == max(b.date for b in all_bars)]
            symbols = sorted({b.symbol for b in latest_bars})
            # Cap at Nifty 500 scope
            if len(symbols) > 500:
                symbols = symbols[:500]

        if not symbols:
            raise ValueError("No symbols to screen")

        # 4. Upsert securities
        securities = await self._upsert_securities(symbols)
        symbol_to_security = {str(s.symbol): s for s in securities}

        # 5. Persist historical OHLCV data
        await self._persist_bars(all_bars, symbol_to_security)

        # 6. Run the screening pipeline via ScreeningOrchestrator
        run_id = await self._run_via_orchestrator(strategy, reference_date)

        _logger.info("execute_screening_completed", run_id=run_id)
        return run_id

    async def _fetch_eod_range(
        self,
        start_date: date,
        end_date: date,
    ) -> list[Any]:
        """Fetch EOD bars for every calendar date in the range.

        Holidays return empty lists and are skipped. Returns a flat list of
        RawBar objects across all fetched trading days.
        """
        bars: list[Any] = []
        current = start_date
        while current <= end_date:
            daily_bars = await self._market_data_provider.fetch_eod(current)
            if daily_bars:
                bars.extend(daily_bars)
                _logger.debug("eod_fetched", date=current.isoformat(), bars=len(daily_bars))
            current += timedelta(days=1)
        return bars

    async def _resolve_strategy(self, strategy_name: str) -> Strategy:
        """Load a strategy from the database by name."""
        strategy_repo = await self._get_strategy_repo()
        strategy = await strategy_repo.get_active(strategy_name)
        if strategy is None:
            msg = f"Strategy not found: {strategy_name}"
            raise RuntimeError(msg)
        return cast(Strategy, strategy)

    async def _get_strategy_repo(self) -> Any:
        """Create a :class:`SqlStrategyRepository` sharing the same session."""
        from momentum25.infrastructure.persistence.repositories.strategy import (
            SqlStrategyRepository,
        )

        session = getattr(self._screening_run_repo, "_session", None)
        if session is None:
            msg = "No session available from screening_run_repo"
            raise RuntimeError(msg)
        return SqlStrategyRepository(session)

    async def _upsert_securities(self, symbols: list[str]) -> list[Security]:
        """Upsert securities and return entities with database IDs.

        Enriches each security with the instrument master's ``listing_date``
        (used by ``HistoricalScreeningUseCase`` to exclude not-yet-listed
        securities from a backtest's universe -- without this, every
        security's ``listing_date`` stays ``None`` and that survivorship-bias
        mitigation silently never filters anything).
        """
        instruments_by_symbol = {
            instrument.symbol: instrument
            for instrument in await self._market_data_provider.fetch_instrument_master()
        }
        securities = [
            Security(
                symbol=Symbol(sym),
                name=instruments_by_symbol[sym].name if sym in instruments_by_symbol else sym,
                isin=instruments_by_symbol[sym].isin if sym in instruments_by_symbol else None,
                listing_date=(
                    instruments_by_symbol[sym].listing_date
                    if sym in instruments_by_symbol
                    else None
                ),
                is_active=True,
            )
            for sym in symbols
        ]
        await self._security_repo.upsert_many(securities)
        await self._commit()

        # Re-fetch to get IDs assigned by the database
        active = await self._security_repo.list_active()
        symbol_map = {str(s.symbol): s for s in active}
        return [
            symbol_map.get(sym, sec)
            for sym, sec in zip(symbols, securities, strict=False)
            if sym in symbol_map
        ]

    async def _persist_bars(
        self,
        bars: list[Any],
        symbol_to_security: dict[str, Security],
    ) -> None:
        """Group raw bars by security and persist them."""
        bars_by_security: dict[int, list[OHLCVBar]] = {}
        for raw in bars:
            security = symbol_to_security.get(raw.symbol)
            if security is None or security.id is None:
                continue
            bars_by_security.setdefault(security.id, []).append(
                OHLCVBar(
                    date=raw.date,
                    open=raw.open,
                    high=raw.high,
                    low=raw.low,
                    close=raw.close,
                    volume=raw.volume,
                    prev_close=raw.prev_close,
                    turnover_value=raw.turnover_value,
                )
            )

        for security_id, security_bars in bars_by_security.items():
            await self._ohlcv_repo.upsert_bars(security_id, security_bars)

        await self._commit()
        _logger.info("history_persisted", securities=len(bars_by_security))

    async def _run_via_orchestrator(
        self,
        strategy: Strategy,
        trading_date: date,
    ) -> int:
        """Delegate the core pipeline to :class:`ScreeningOrchestrator`."""
        from momentum25.application.use_cases.screening_orchestrator import (
            ScreeningOrchestrator,
        )

        orchestrator = ScreeningOrchestrator(
            security_repo=self._security_repo,
            ohlcv_repo=self._ohlcv_repo,
            screening_run_repo=self._screening_run_repo,
            market_data_provider=self._market_data_provider,
            indicator_pipeline=self._indicator_pipeline,
            strategy_engine=self._strategy_engine,
            strategy=strategy,
            strategy_repo=None,
        )

        await orchestrator.run_daily_screening(trading_date)

        # Return the id of the newly completed run
        runs, _ = await self._screening_run_repo.list_runs("completed", 1, 0)
        if runs and runs[0].id is not None:
            return int(runs[0].id)
        msg = "No completed runs found after screening"
        raise RuntimeError(msg)

    async def _commit(self) -> None:
        """Commit the current unit of work."""
        session = getattr(self._screening_run_repo, "_session", None)
        if session is not None:
            await session.commit()