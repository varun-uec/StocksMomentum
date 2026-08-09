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
from momentum25.infrastructure.calendar.nse_calendar import get_nse_trading_calendar

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
        force: bool = False,
        existing_run_id: int | None = None,
    ) -> int:
        """Execute the full end-to-end screening pipeline.

        Args:
            strategy_name: Name of the strategy to run (loaded from DB).
            target_symbols: Optional list of symbols to screen. If ``None``,
                the universe is derived from the latest EOD file.
            force: If ``True``, fetches the full ``_MIN_HISTORY_CALENDAR_DAYS``
                window regardless of what is already persisted. If ``False``
                (default), fetches only sessions after the latest persisted
                bar (Phase 1.6) -- a full re-fetch on every call was 501
                sequential NSE round-trips, most of them for non-trading days.
            existing_run_id: If provided, the screening run updates this
                already-created row instead of creating a new one (background
                execution path, Phase 1.6).

        Returns:
            The id of the created (or adopted) screening run.

        Raises:
            :class:`RuntimeError` if the strategy is not found.
        """
        _logger.info(
            "execute_screening_started",
            strategy=strategy_name,
            target_symbols=target_symbols,
            force=force,
        )

        # 1. Resolve the strategy
        strategy = await self._resolve_strategy(strategy_name)

        reference_date = date.today()
        if force:
            start_date = reference_date - timedelta(days=_MIN_HISTORY_CALENDAR_DAYS)
        else:
            latest = await self._ohlcv_repo.latest_date()
            start_date = (
                latest + timedelta(days=1)
                if latest is not None
                else reference_date - timedelta(days=_MIN_HISTORY_CALENDAR_DAYS)
            )

        # 2. Fetch EOD bars for the (possibly incremental) window
        all_bars = (
            await self._fetch_eod_range(start_date, reference_date)
            if start_date <= reference_date
            else []
        )

        if not all_bars:
            # An incremental run with nothing new since the last ingest is
            # not an error -- the universe is already persisted from a prior
            # run and the orchestrator resolves it independently via
            # ``security_repo.list_active()``. Only a genuinely empty
            # database (no strategy has ever ingested anything) is an error.
            if force or not await self._security_repo.list_active():
                raise ValueError("No market data available for screening")
            _logger.info("execute_screening_no_new_bars", start_date=start_date.isoformat())
        else:
            # 3. Resolve the symbol universe.
            #
            # Every EQ-series symbol trading on the latest available session is
            # ingested. Admission to the *screened* universe is decided downstream by
            # the strategy's declared liquidity floor (``config.universe``), recorded
            # per security as an explainable ``UniverseMembership`` reason.
            #
            # Phase 0.1: this previously ended with ``symbols = symbols[:500]`` under a
            # "Cap at Nifty 500 scope" comment. Because ``symbols`` is sorted
            # alphabetically, that kept the first 500 tickers by name (roughly
            # 20MICRONS→ELGIEQUIP) and silently dropped every symbol later in the
            # alphabet — it was never the Nifty 500, and no index-constituent source
            # exists in this codebase to build one from (nsemine exposes no
            # constituents endpoint; see docs/research). Screening the full EQ market
            # and gating on declared liquidity is both honest about what it does and
            # closer to the documented intent than an alphabetical truncation.
            if target_symbols:
                symbols = target_symbols
            else:
                latest_bars = [b for b in all_bars if b.date == max(b.date for b in all_bars)]
                symbols = sorted({b.symbol for b in latest_bars})

            if not symbols:
                raise ValueError("No symbols to screen")

            # 4. Upsert securities
            securities = await self._upsert_securities(symbols)
            symbol_to_security = {str(s.symbol): s for s in securities}

            # 5. Persist historical OHLCV data
            await self._persist_bars(all_bars, symbol_to_security)

        # 6. Run the screening pipeline via ScreeningOrchestrator.
        #
        # Screen the latest session that actually has data, not the wall-clock
        # date: on a weekend, holiday, or before the bhavcopy publishes,
        # reference_date matches no bar and the orchestrator's admission gate
        # (bars[-1].date != trading_date) drops every security as
        # no_bar_on_trading_date -- the universe collapses to zero scored,
        # zero passed, zero failed with no error surfaced.
        latest_bar_date = await self._ohlcv_repo.latest_date()
        screening_date = latest_bar_date or reference_date
        run_id = await self._run_via_orchestrator(strategy, screening_date, existing_run_id)

        _logger.info("execute_screening_completed", run_id=run_id)
        return run_id

    async def _fetch_eod_range(
        self,
        start_date: date,
        end_date: date,
    ) -> list[Any]:
        """Fetch EOD bars for every trading session in the range.

        Non-sessions (weekends and NSE holidays, Phase 1.5) are skipped
        without a network call -- previously every calendar day was fetched,
        including ~30% that could only ever return an empty result. Returns a
        flat list of RawBar objects across all fetched trading days.
        """
        bars: list[Any] = []
        calendar = get_nse_trading_calendar()
        for session in calendar.sessions_between(start_date, end_date):
            # ``fetch_eod_full`` rather than ``fetch_eod``: identical bars plus the
            # ``turnover_value`` and ``prev_close`` columns the plain variant drops.
            # Real turnover is required by the strategy's declared liquidity floor
            # (Phase 0.1) — without it every security resolves to
            # ``insufficient_turnover_data`` and the universe collapses to empty.
            daily_bars = await self._market_data_provider.fetch_eod_full(session)
            if daily_bars:
                bars.extend(daily_bars)
                _logger.debug("eod_fetched", date=session.isoformat(), bars=len(daily_bars))
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
        existing_run_id: int | None = None,
    ) -> int:
        """Delegate the core pipeline to :class:`ScreeningOrchestrator`."""
        from momentum25.application.use_cases.screening_orchestrator import (
            ScreeningOrchestrator,
        )

        orchestrator = ScreeningOrchestrator(
            security_repo=self._security_repo,
            ohlcv_repo=self._ohlcv_repo,
            screening_run_repo=self._screening_run_repo,
            indicator_pipeline=self._indicator_pipeline,
            strategy_engine=self._strategy_engine,
            strategy=strategy,
            strategy_repo=None,
        )

        await orchestrator.run_daily_screening(trading_date, existing_run_id=existing_run_id)

        if existing_run_id is not None:
            return existing_run_id

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