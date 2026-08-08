"""API routers, aggregated into a single versioned router."""

from fastapi import APIRouter

from momentum25.infrastructure.config.settings import get_settings
from momentum25.interface.api.routers import (
    health,
    rankings,
    research,
    runs,
    securities,
    stocks,
    strategies,
    validation,
)

api_router = APIRouter(prefix=get_settings().api_v1_prefix)
api_router.include_router(health.router)
api_router.include_router(rankings.router)
api_router.include_router(research.router)
api_router.include_router(stocks.router)
api_router.include_router(runs.router)
api_router.include_router(strategies.router)
api_router.include_router(securities.router)
api_router.include_router(validation.router)

__all__ = ["api_router"]
