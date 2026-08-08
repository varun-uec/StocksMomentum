"""Ranking DTOs."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from momentum25.application.dto.runs import RunDTO


class RankingItemDTO(BaseModel):
    """A single ranked stock row."""

    rank: int
    symbol: str
    name: str
    momentum_score: Decimal
    buy_setup_score: Decimal
    sector: str | None = None
    rs_rating: int | None = None
    explanation: dict[str, Any] | None = None


class RankingsResponseDTO(BaseModel):
    """A run plus its ranked items."""

    run: RunDTO | None = None
    items: list[RankingItemDTO]
    total: int
    limit: int = 50
    offset: int = 0