"""Watchlist DTOs — a row per tracked symbol, enriched with live/run data."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class WatchlistItemDTO(BaseModel):
    """One tracked symbol with its momentum snapshot.

    ``in_latest_run`` distinguishes a symbol persisted in the strategy's
    latest completed run (fast path: read straight from ``screening_results``)
    from one evaluated live for this response (the symbol was skipped or
    admitted after the last run) -- both are real, current values, but only
    the former carries a ``rank``/``rank_change`` since ranking is relative to
    a run's whole universe.
    """

    symbol: str
    in_latest_run: bool
    momentum_score: Decimal | None = None
    buy_setup_score: Decimal | None = None
    rank: int | None = None
    rank_change: int | None = None
    rs_rating: int | None = None
    pct_below_high_52w: Decimal | None = None
    close: Decimal | None = None
    change_pct: Decimal | None = None


class WatchlistDetailResponseDTO(BaseModel):
    """The enriched watchlist for one strategy."""

    strategy: str
    run_id: int | None
    items: list[WatchlistItemDTO]
