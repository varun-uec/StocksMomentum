"""Market Synchronisation Service — bulk NSE data ingestion.

Loops over a target universe of NSE symbols, fetches their true historical prices
via :class:`NSEMarketDataClient`, upserts the bars into PostgreSQL via
:class:`SqlOHLCVRepository`, and computes indicators via
:class:`IndicatorPipelineImpl`.

Rule evaluation is deliberately not done here. An earlier version of this
class re-implemented the 8 Minervini trend-template rules by hand (duplicate
business logic, forbidden by CLAUDE.md) and evaluated them against
``get_series(security_id=0, ...)`` -- a hardcoded id, always wrong. It went
undetected because this class has never had a caller. Single-symbol
evaluation now goes through the real :class:`StrategyEngine`, via
``GetLiveStockAnalysis`` (``application/use_cases/stocks.py``), which reuses
``build_evaluation_context`` from the daily orchestrator.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from momentum25.domain.entities.market_data import OHLCVBar
from momentum25.domain.entities.security import Security
from momentum25.domain.value_objects.types import Symbol
from momentum25.infrastructure.persistence.repositories.ohlcv import SqlOHLCVRepository
from momentum25.infrastructure.persistence.repositories.security import SqlSecurityRepository
from momentum25.infrastructure.pipelines.indicator_pipeline import IndicatorPipelineImpl
from momentum25.infrastructure.providers.nse_client import NSEMarketDataClient

_logger = get_logger("market_sync")

# How many trading days of history to fetch per symbol (275 minimum for 200 SMA + slope)
_MIN_HISTORY_DAYS = 275

# Buffer to ensure we exceed the minimum (trading days, not calendar)
_HISTORY_LOOKBACK_DAYS = 500

# Maximum concurrent NSE requests
_MAX_CONCURRENT_SYMBOLS = 10


class MarketSyncService:
    """Orchestrates bulk live NSE data ingestion and indicator computation.

    Workflow:
        1. Fetch the active NSE symbol universe via :class:`NSEMarketDataClient`.
        2. Upsert securities into the database.
        3. For each symbol, fetch multi-month historical OHLCV bars.
        4. Upsert bars into the ``ohlcv_daily`` table.
        5. Compute technical indicators via :class:`IndicatorPipelineImpl`.
        6. Log results for observability.

    Attributes:
        nse_client: The NSE market data client.
        security_repo: Repository for instrument master persistence.
        ohlcv_repo: Repository for OHLCV bar persistence.
        indicator_pipeline: The technical indicator computation pipeline.
        semaphore: Concurrency throttle for symbol processing.
    """

    def __init__(
        self,
        session: AsyncSession,
        nse_client: NSEMarketDataClient | None = None,
        max_concurrent: int = _MAX_CONCURRENT_SYMBOLS,
    ) -> None:
        """Initialise the market sync service with its collaborators.

        Args:
            session: An async SQLAlchemy session for persistence.
            nse_client: An NSE market data client (created if not provided).
            max_concurrent: Maximum number of symbols to process concurrently.
        """
        self._session = session
        self._nse_client = nse_client or NSEMarketDataClient()
        self._security_repo = SqlSecurityRepository(session)
        self._ohlcv_repo = SqlOHLCVRepository(session)
        self._indicator_pipeline = IndicatorPipelineImpl(session)
        self._semaphore = asyncio.Semaphore(max_concurrent)
        _logger.info(
            "market_sync_initialised",
            max_concurrent=max_concurrent,
        )

    async def sync_and_evaluate(
        self,
        reference_date: date | None = None,
        target_symbols: list[str] | None = None,
    ) -> dict[str, Any]:
        """Execute the full sync-and-evaluate pipeline.

        Args:
            reference_date: The date to use as "today" for indicator computation
                (defaults to actual today).
            target_symbols: Optional subset of symbols to process. If not provided,
                fetches the entire active universe from NSE.

        Returns:
            A summary dictionary with counts of processed, passed, failed symbols
            and timing information.
        """
        ref_date = reference_date or date.today()
        _logger.info("market_sync_started", reference_date=ref_date.isoformat())

        # Step 1: Resolve the symbol universe
        if target_symbols:
            symbols = target_symbols
            _logger.info("using_target_symbols", count=len(symbols))
        else:
            symbols = await self._nse_client.fetch_active_symbols()
            _logger.info("fetched_active_universe", count=len(symbols))

        if not symbols:
            _logger.warning("empty_symbol_universe")
            return {
                "reference_date": ref_date.isoformat(),
                "total_symbols": 0,
                "processed": 0,
                "passed_trend_template": 0,
                "failed_trend_template": 0,
                "errors": [],
            }

        # Step 2: Upsert securities into the database
        securities = await self._upsert_securities(symbols)
        symbol_to_security = {str(s.symbol): s for s in securities}

        # Steps 3-6: Process each symbol concurrently
        results: list[dict[str, Any]] = []
        errors: list[str] = []

        async def _process_symbol(symbol: str) -> dict[str, Any] | None:
            async with self._semaphore:
                try:
                    return await self._sync_and_evaluate_one(
                        symbol=symbol,
                        security=symbol_to_security.get(symbol),
                        reference_date=ref_date,
                    )
                except Exception as exc:
                    error_msg = f"{symbol}: {exc}"
                    _logger.error("symbol_processing_failed", symbol=symbol, error=str(exc))
                    errors.append(error_msg)
                    return None

        coros = [_process_symbol(sym) for sym in symbols if sym in symbol_to_security]
        task_results = await asyncio.gather(*coros)
        results = [r for r in task_results if r is not None]

        # Step 7: Aggregate summary
        summary: dict[str, Any] = {
            "reference_date": ref_date.isoformat(),
            "total_symbols": len(symbols),
            "processed": len(results),
            "insufficient_history": sum(
                1 for r in results if r.get("insufficient_history", False)
            ),
            "errors": errors,
        }

        _logger.info("market_sync_completed", **summary)
        return summary

    async def _sync_and_evaluate_one(
        self,
        symbol: str,
        security: Security | None,
        reference_date: date,
    ) -> dict[str, Any]:
        """Process a single symbol: fetch, persist, compute, evaluate.

        Args:
            symbol: The NSE trading symbol.
            security: The domain Security entity (or None if not in DB).
            reference_date: The reference date for indicator computation.

        Returns:
            A dictionary with the symbol's processing results.
        """
        result: dict[str, Any] = {
            "symbol": symbol,
            "bars_fetched": 0,
            "bars_upserted": 0,
            "insufficient_history": False,
            "indicators": {},
        }

        # Fetch historical bars
        start_date = reference_date - timedelta(days=_HISTORY_LOOKBACK_DAYS)
        raw_bars = await self._nse_client.fetch_historical_bars(
            symbol=symbol,
            start_date=start_date,
            end_date=reference_date,
        )

        if not raw_bars:
            _logger.warning("no_bars_fetched", symbol=symbol)
            result["insufficient_history"] = True
            return result

        result["bars_fetched"] = len(raw_bars)

        # Convert to domain OHLCVBar objects
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

        # Upsert bars if we have a security id
        if security is not None and security.id is not None:
            upserted = await self._ohlcv_repo.upsert_bars(security.id, bars)
            result["bars_upserted"] = upserted
            await self._session.commit()

            # Compute indicators
            indicators = await self._indicator_pipeline.compute(
                symbol=symbol,
                reference_date=reference_date,
                config={},
            )

            result["indicators"] = {
                "sma50": str(indicators.sma50) if indicators.sma50 is not None else None,
                "sma150": str(indicators.sma150) if indicators.sma150 is not None else None,
                "sma200": str(indicators.sma200) if indicators.sma200 is not None else None,
                "sma200_slope_pct": (
                    str(indicators.sma200_slope_pct)
                    if indicators.sma200_slope_pct is not None
                    else None
                ),
                "high_52w": str(indicators.high_52w) if indicators.high_52w is not None else None,
                "low_52w": str(indicators.low_52w) if indicators.low_52w is not None else None,
                "rs_rating": indicators.rs_rating,
            }

            # Check if we have sufficient history for trend template
            result["insufficient_history"] = indicators.sma200 is None
        else:
            _logger.warning("security_not_in_database", symbol=symbol)

        return result

    async def _upsert_securities(self, symbols: list[str]) -> list[Security]:
        """Upsert a list of symbols into the securities table.

        Creates placeholder Security entities for each symbol and persists them
        via the security repository.

        Args:
            symbols: A list of NSE trading symbols to upsert.

        Returns:
            The list of domain Security entities (with their database IDs populated).
        """
        securities = [
            Security(
                symbol=Symbol(sym),
                name=sym,
                is_active=True,
            )
            for sym in symbols
        ]

        await self._security_repo.upsert_many(securities)
        await self._session.commit()

        # Re-fetch to get database IDs
        active = await self._security_repo.list_active()
        symbol_map = {str(s.symbol): s for s in active}
        return [symbol_map.get(sym, sec) for sym, sec in zip(symbols, securities) if sym in symbol_map]