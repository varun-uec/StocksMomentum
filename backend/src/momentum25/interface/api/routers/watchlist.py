"""Watchlist endpoints (Phase 6.9) — a single global tracked-symbol list."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from momentum25.application.use_cases.watchlist import (
    AddToWatchlist,
    GetWatchlist,
    RemoveFromWatchlist,
)
from momentum25.interface.api.dependencies import (
    get_add_to_watchlist,
    get_get_watchlist,
    get_remove_from_watchlist,
)

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


class WatchlistResponse(BaseModel):
    """The watchlisted symbols."""

    symbols: list[str]


@router.get("", response_model=WatchlistResponse)
async def read_watchlist(
    use_case: Annotated[GetWatchlist, Depends(get_get_watchlist)],
) -> WatchlistResponse:
    """Return every watchlisted symbol, oldest addition first."""
    return WatchlistResponse(symbols=await use_case.execute())


@router.post("/{symbol}", response_model=WatchlistResponse)
async def add_watchlist_item(
    symbol: str,
    use_case: Annotated[AddToWatchlist, Depends(get_add_to_watchlist)],
    read: Annotated[GetWatchlist, Depends(get_get_watchlist)],
) -> WatchlistResponse:
    """Add a symbol to the watchlist (idempotent) and return the new list."""
    await use_case.execute(symbol)
    return WatchlistResponse(symbols=await read.execute())


@router.delete("/{symbol}", response_model=WatchlistResponse)
async def remove_watchlist_item(
    symbol: str,
    use_case: Annotated[RemoveFromWatchlist, Depends(get_remove_from_watchlist)],
    read: Annotated[GetWatchlist, Depends(get_get_watchlist)],
) -> WatchlistResponse:
    """Remove a symbol from the watchlist (idempotent) and return the new list."""
    await use_case.execute(symbol)
    return WatchlistResponse(symbols=await read.execute())
