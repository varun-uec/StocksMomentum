"""RefreshLatestMarketData — pull the latest completed session's EOD bars on demand.

A thin orchestration layer over the existing ingestion primitives: the two
bulk bhavcopy providers, the trading calendar, the security universe and the
idempotent OHLCV upsert. It fetches exactly one session (the latest completed
one), maps its bars onto the active universe of the exchange that produced
them, and writes them. It never screens, never backfills and never invents a
bar it did not receive.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date, timedelta
from time import perf_counter

from structlog import get_logger

from momentum25.application.dto.market_data import (
    ExchangeRefreshResult,
    RefreshSummary,
)
from momentum25.domain.entities.market_data import OHLCVBar
from momentum25.domain.entities.security import Security
from momentum25.domain.ports.clock import Clock
from momentum25.domain.ports.market_data import MarketDataProvider, RawBar
from momentum25.domain.ports.repositories import OHLCVRepository, SecurityRepository
from momentum25.domain.ports.trading_calendar import TradingCalendar

_logger = get_logger("refresh_latest_market_data")

# How far back to look for the latest completed session. Ten calendar days
# clears the longest NSE/BSE holiday cluster plus a weekend.
_LOOKBACK_DAYS = 10


class RefreshLatestMarketData:
    """Ingest the latest completed trading session for the requested exchanges."""

    def __init__(
        self,
        providers: dict[str, MarketDataProvider],
        security_repo: SecurityRepository,
        ohlcv_repo: OHLCVRepository,
        calendar: TradingCalendar,
        clock: Clock,
    ) -> None:
        """Bind the providers (keyed by exchange) and the repositories."""
        self._providers = providers
        self._security_repo = security_repo
        self._ohlcv_repo = ohlcv_repo
        self._calendar = calendar
        self._clock = clock

    async def execute(self, exchanges: list[str]) -> RefreshSummary:
        """Refresh the latest completed session for each requested exchange.

        Exchanges are processed in the order given, de-duplicated. A provider
        failure on one exchange is recorded on that exchange's result and does
        not stop the others.
        """
        started = perf_counter()
        target_date = self._latest_completed_session()
        summary = RefreshSummary(target_date=target_date)

        securities = await self._security_repo.list_active()
        seen: set[str] = set()
        for exchange in exchanges:
            if exchange in seen:
                continue
            seen.add(exchange)
            summary.results.append(await self._refresh_exchange(exchange, target_date, securities))

        summary.duration_seconds = perf_counter() - started
        _logger.info(
            "refresh_latest_market_data_completed",
            target_date=target_date.isoformat(),
            status=summary.overall_status,
            duration_seconds=round(summary.duration_seconds, 3),
        )
        return summary

    def _latest_completed_session(self) -> date:
        """Return the last trading session on or before yesterday.

        Yesterday, not today: today's session may still be open and the
        bhavcopy for it is not published until after the close.
        """
        today = self._clock.today()
        sessions = self._calendar.sessions_between(
            today - timedelta(days=_LOOKBACK_DAYS), today - timedelta(days=1)
        )
        if not sessions:
            msg = f"No trading session in the {_LOOKBACK_DAYS} days before {today.isoformat()}."
            raise RuntimeError(msg)
        return sessions[-1]

    async def _refresh_exchange(
        self, exchange: str, target_date: date, securities: list[Security]
    ) -> ExchangeRefreshResult:
        """Fetch, map and persist one exchange's bars for ``target_date``."""
        result = ExchangeRefreshResult(exchange=exchange)
        provider = self._providers.get(exchange)
        if provider is None:
            result.provider_error = f"No provider configured for exchange {exchange}."
            return result

        try:
            bars = await self._fetch(provider, target_date)
        except Exception as exc:  # provider failures are reported, never fatal
            result.provider_error = f"{type(exc).__name__}: {exc}"
            _logger.warning(
                "refresh_provider_failed",
                exchange=exchange,
                date=target_date.isoformat(),
                error=str(exc),
            )
            return result

        result.bars_fetched = len(bars)
        security_id_by_symbol: dict[str, int] = {
            str(s.symbol): s.id
            for s in securities
            if s.exchange == exchange and s.id is not None
        }
        if not security_id_by_symbol:
            result.warnings.append(
                f"No active securities are registered on {exchange}; nothing to map bars onto."
            )

        bars_by_security: dict[int, list[OHLCVBar]] = {}
        for raw in bars:
            security_id = security_id_by_symbol.get(raw.symbol)
            if security_id is None:
                result.securities_unmapped += 1
                continue
            result.securities_matched += 1
            bars_by_security.setdefault(security_id, []).append(_to_bar(raw))

        result.securities_missing = len(security_id_by_symbol) - len(bars_by_security)
        result.rows_written = await self._ohlcv_repo.upsert_bars_batch(bars_by_security)
        await self._commit()

        if not bars:
            result.warnings.append(
                f"{exchange} returned no bars for {target_date.isoformat()}."
            )
        return result

    @staticmethod
    async def _fetch(provider: MarketDataProvider, target_date: date) -> list[RawBar]:
        """Fetch a session's bars, preferring the turnover-carrying variant.

        The NSE provider's ``fetch_eod`` drops ``turnover_value`` and
        ``prev_close``; ``fetch_eod_full`` returns the same bars with both.
        The upsert overwrites those columns, so fetching the lean variant would
        blank out the turnover the liquidity gate reads. The BSE provider
        carries both on ``fetch_eod`` and has no ``_full`` variant.
        """
        fetch: Callable[[date], Awaitable[list[RawBar]]] = getattr(
            provider, "fetch_eod_full", provider.fetch_eod
        )
        return await fetch(target_date)

    async def _commit(self) -> None:
        """Commit the current unit of work."""
        session = getattr(self._ohlcv_repo, "_session", None)
        if session is not None:
            await session.commit()


def _to_bar(raw: RawBar) -> OHLCVBar:
    """Map a provider bar onto the domain bar. ``adj_close`` is left to the upsert."""
    return OHLCVBar(
        date=raw.date,
        open=raw.open,
        high=raw.high,
        low=raw.low,
        close=raw.close,
        volume=raw.volume,
        prev_close=raw.prev_close,
        turnover_value=raw.turnover_value,
    )
