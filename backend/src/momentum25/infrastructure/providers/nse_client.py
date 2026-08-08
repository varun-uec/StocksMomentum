"""NSE market-data client — convenience extension of :class:`BhavcopyProvider`.

Adds per-symbol historical-bar fetching and active-symbol listing on top of the
:class:`MarketDataProvider` port implementation, for :class:`MarketSyncService`
(``app/services/market_sync.py``). All NSE scraping logic lives in
:mod:`momentum25.infrastructure.providers.bhavcopy` to avoid duplicating the
adapter; this module only adds the two extra methods that provider doesn't need.
"""

from __future__ import annotations

import asyncio
import time
from datetime import date, datetime
from typing import Any

from nsemine import historical

from momentum25.domain.ports.market_data import RawBar
from momentum25.infrastructure.logging.setup import get_logger
from momentum25.infrastructure.providers.bhavcopy import BhavcopyProvider
from momentum25.infrastructure.resilience import CircuitBreaker, resilient

_logger = get_logger("nse_client")

# NSE will block naive per-request scraping (backlog 1.3): a circuit breaker
# stops hammering a failing endpoint, a semaphore bounds concurrent fetches,
# and a minimum interval between dispatches throttles burst traffic (e.g. a
# scheduler job fanning out over hundreds of symbols).
_historical_breaker = CircuitBreaker("nse_historical", failure_threshold=5, recovery_timeout=60.0)
_fetch_semaphore = asyncio.Semaphore(5)
_MIN_INTERVAL_SECONDS = 0.25
_throttle_lock = asyncio.Lock()
_last_dispatch_time = 0.0


@resilient(
    "nse_historical_fetch",
    max_attempts=3,
    min_wait=2.0,
    max_wait=10.0,
    circuit_breaker=_historical_breaker,
    timeout_seconds=30.0,
)
async def _fetch_historical_dataframe(symbol: str, start_dt: datetime, end_dt: datetime) -> Any:
    """Retryable, circuit-breaker-guarded call to the NSE historical-data source."""
    return await asyncio.to_thread(
        historical.get_stock_historical_data,
        stock_symbol=symbol,
        start_datetime=start_dt,
        end_datetime=end_dt,
        interval="D",
    )


class NSEMarketDataClient(BhavcopyProvider):
    """:class:`BhavcopyProvider` plus per-symbol historical fetch and symbol listing."""

    async def fetch_historical_bars(
        self,
        symbol: str,
        start_date: date,
        end_date: date | None = None,
    ) -> list[RawBar]:
        """Fetch multi-month daily-interval OHLCV bars for a single symbol."""
        end = end_date or date.today()
        start_dt = datetime.combine(start_date, datetime.min.time())
        end_dt = datetime.combine(end, datetime.min.time())
        bars: list[RawBar] = []
        try:
            async with _fetch_semaphore:
                await self._throttle()
                df = await _fetch_historical_dataframe(symbol, start_dt, end_dt)
        except Exception as exc:
            _logger.warning(
                "nse_historical_fetch_failed",
                symbol=symbol,
                start=start_date.isoformat(),
                end=end.isoformat(),
                error=str(exc),
            )
            return bars

        if df is not None and not df.empty:
            for _, row in df.iterrows():
                try:
                    parsed_date = self._to_date(row.get("datetime"))
                    if parsed_date is None:
                        continue
                    bars.append(
                        RawBar(
                            symbol=symbol.strip().upper(),
                            date=parsed_date,
                            open=self._to_decimal(row.get("open")),
                            high=self._to_decimal(row.get("high")),
                            low=self._to_decimal(row.get("low")),
                            close=self._to_decimal(row.get("close")),
                            volume=int(row.get("volume", 0) or 0),
                        )
                    )
                except (ValueError, TypeError) as exc:
                    _logger.warning("nse_historical_row_skipped", symbol=symbol, error=str(exc))
        bars.sort(key=lambda b: b.date)
        return bars

    @staticmethod
    async def _throttle() -> None:
        """Enforce a minimum interval between dispatched NSE fetches."""
        global _last_dispatch_time
        async with _throttle_lock:
            elapsed = time.monotonic() - _last_dispatch_time
            if elapsed < _MIN_INTERVAL_SECONDS:
                await asyncio.sleep(_MIN_INTERVAL_SECONDS - elapsed)
            _last_dispatch_time = time.monotonic()

    async def fetch_active_symbols(self) -> list[str]:
        """Return a sorted list of all active NSE equity symbols."""
        instruments = await self.fetch_instrument_master()
        symbols = sorted({inst.symbol for inst in instruments})
        _logger.info("nse_active_symbols", count=len(symbols))
        return symbols
