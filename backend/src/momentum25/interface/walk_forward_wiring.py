"""Composition of the walk-forward runner against real Postgres data.

Both entry points -- the ``walk-forward`` CLI command and the ``/backtest``
API route -- build the runner the same way. The wiring lives here once so the
two surfaces can never drift apart on which providers, which benchmark, or
which price lookback window the backtest uses.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from momentum25.application.use_cases.walk_forward import WalkForwardRunner
from momentum25.infrastructure.calendar.nse_calendar import get_nse_trading_calendar
from momentum25.infrastructure.persistence.database import get_database
from momentum25.infrastructure.persistence.repositories.walk_forward_market_data import (
    SqlBenchmarkProvider,
    SqlPriceHistoryProvider,
    SqlSurvivorshipEligibilityProvider,
)

DEFAULT_INITIAL_CAPITAL = Decimal("1000000")
BENCHMARK_SYMBOL = "NIFTY500"
_PRICE_LOOKBACK_DAYS = 400  # covers the 12m momentum lookback


async def build_walk_forward_runner(start: date, end: date) -> WalkForwardRunner:
    """Load the point-in-time providers for ``[start, end]`` and bind a runner."""
    database = get_database()
    price_load_start = start - timedelta(days=_PRICE_LOOKBACK_DAYS)
    async with database.session() as session:
        prices = await SqlPriceHistoryProvider.load(session, price_load_start, end)
        benchmark = await SqlBenchmarkProvider.load(
            session, BENCHMARK_SYMBOL, start, end
        )
        universe = await SqlSurvivorshipEligibilityProvider.load(session)
    return WalkForwardRunner(
        calendar=get_nse_trading_calendar(),
        prices=prices,
        universe=universe,
        benchmark=benchmark,
    )
