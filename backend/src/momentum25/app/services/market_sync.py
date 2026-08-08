"""Market Synchronisation Service — live NSE data pipeline orchestration.

Loops over a target universe of NSE symbols, fetches their true historical prices
via :class:`NSEMarketDataClient`, upserts the bars into PostgreSQL via
:class:`SqlOHLCVRepository`, and pipelines the computed indicators through our
existing Minervini TrendTemplate rule engine.

This is the hexagonal orchestration integration layer that replaces mock data
with live, production-ready asynchronous market data.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from momentum25.domain.entities.market_data import OHLCVBar
from momentum25.domain.entities.security import Security
from momentum25.domain.value_objects.indicators import IndicatorSet
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
    """Orchestrates live NSE data ingestion, persistence, and rule evaluation.

    Workflow:
        1. Fetch the active NSE symbol universe via :class:`NSEMarketDataClient`.
        2. Upsert securities into the database.
        3. For each symbol, fetch multi-month historical OHLCV bars.
        4. Upsert bars into the ``ohlcv_daily`` table.
        5. Compute technical indicators via :class:`IndicatorPipelineImpl`.
        6. Evaluate the Minervini TrendTemplate rules.
        7. Log pass/fail results for observability.

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
        passed = sum(1 for r in results if r.get("trend_template_passed", False))
        failed = sum(1 for r in results if r.get("trend_template_passed") is False)

        summary: dict[str, Any] = {
            "reference_date": ref_date.isoformat(),
            "total_symbols": len(symbols),
            "processed": len(results),
            "passed_trend_template": passed,
            "failed_trend_template": failed,
            "insufficient_history": sum(
                1 for r in results if r.get("insufficient_history", False)
            ),
            "errors": errors,
            "symbols_passed": [r["symbol"] for r in results if r.get("trend_template_passed")],
        }

        _logger.info(
            "market_sync_completed",
            **{k: v for k, v in summary.items() if k != "symbols_passed"},
        )
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
            "trend_template_passed": False,
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
            if indicators.sma200 is not None:
                result["insufficient_history"] = False
                # Quick trend template evaluation based on available indicators
                passed = await self._evaluate_trend_template(symbol, indicators)
                result["trend_template_passed"] = passed
            else:
                result["insufficient_history"] = True
        else:
            _logger.warning("security_not_in_database", symbol=symbol)

        return result

    async def _evaluate_trend_template(
        self,
        symbol: str,
        indicators: IndicatorSet,
    ) -> bool:
        """Evaluate the Minervini trend template rules against computed indicators.

        Checks the core 8 rules:
            1. Close > SMA150 AND Close > SMA200
            2. SMA150 > SMA200
            3. SMA200 trending up (slope > 0)
            4. SMA50 > SMA150 AND SMA50 > SMA200
            5. Close > SMA50
            6. Close >= 52w Low * 1.30
            7. Close >= 52w High * 0.75
            8. RS Rating >= 70 (uses stub rating as baseline)

        Args:
            symbol: The trading symbol (for logging).
            indicators: The computed indicator set.

        Returns:
            ``True`` if all 8 trend template rules pass, ``False`` otherwise.
        """
        close = None
        try:
            series = await self._ohlcv_repo.get_series(
                security_id=0, lookback_days=1, as_of=indicators.as_of
            )
            close = series.latest.close if series.latest else None
        except Exception:
            _logger.warning("could_not_get_latest_close", symbol=symbol)

        if close is None:
            _logger.warning("no_close_price_available", symbol=symbol)
            return False

        rules: dict[str, bool] = {}

        # R1: Close > SMA150 AND Close > SMA200
        r1 = all(
            x is not None and close > x
            for x in [indicators.sma150, indicators.sma200]
        )
        rules["price_above_long_mas"] = r1

        # R2: SMA150 > SMA200
        r2 = (
            indicators.sma150 is not None
            and indicators.sma200 is not None
            and indicators.sma150 > indicators.sma200
        )
        rules["ma150_above_ma200"] = r2

        # R3: SMA200 trending up
        r3 = (
            indicators.sma200_slope_pct is not None
            and indicators.sma200_slope_pct > Decimal("0")
        )
        rules["ma200_trending_up"] = r3

        # R4: SMA50 > SMA150 AND SMA50 > SMA200
        r4 = all(
            x is not None and indicators.sma50 is not None and indicators.sma50 > x
            for x in [indicators.sma150, indicators.sma200]
        )
        rules["ma50_alignment"] = r4

        # R5: Close > SMA50
        r5 = indicators.sma50 is not None and close > indicators.sma50
        rules["price_above_ma50"] = r5

        # R6: Close >= 52w Low * 1.30
        r6 = (
            indicators.low_52w is not None
            and close >= indicators.low_52w * Decimal("1.30")
        )
        rules["above_52w_low_30pct"] = r6

        # R7: Close >= 52w High * 0.75
        r7 = (
            indicators.high_52w is not None
            and close >= indicators.high_52w * Decimal("0.75")
        )
        rules["within_52w_high_25pct"] = r7

        # R8: RS Rating >= 70 (using stub rating from indicator pipeline)
        r8 = indicators.rs_rating is not None and indicators.rs_rating >= 70
        rules["rs_rating_gte_70"] = r8

        all_passed = all(rules.values())
        passed_count = sum(rules.values())

        _logger.info(
            "trend_template_evaluation",
            symbol=symbol,
            passed=all_passed,
            passed_count=passed_count,
            rules=rules,
        )

        return all_passed

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