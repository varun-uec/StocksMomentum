"""API routers, aggregated into a single versioned router."""

from fastapi import APIRouter

from momentum25.infrastructure.config.settings import get_settings
from momentum25.interface.api.routers import (
    chart_patterns,
    elliott_wave,
    health,
    indices,
    market,
    market_data,
    rankings,
    research,
    runs,
    securities,
    stocks,
    strategies,
    validation,
    watchlist,
)

api_router = APIRouter(prefix=get_settings().api_v1_prefix)
api_router.include_router(health.router)
api_router.include_router(market.router)
api_router.include_router(rankings.router)
api_router.include_router(research.router)
api_router.include_router(stocks.router)
api_router.include_router(runs.router)
api_router.include_router(strategies.router)
api_router.include_router(securities.router)
api_router.include_router(validation.router)
api_router.include_router(watchlist.router)
api_router.include_router(elliott_wave.router)
api_router.include_router(chart_patterns.router)
api_router.include_router(indices.router)
api_router.include_router(market_data.router)

__all__ = ["api_router"]
