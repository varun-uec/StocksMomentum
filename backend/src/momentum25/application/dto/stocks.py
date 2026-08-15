"""Stock score/rank history DTOs.

``/stocks/{symbol}`` returns the domain :class:`StockExplanation` directly.
That dataclass *is* the explainability contract -- it is what the strategy
engine produces, what the frontend consumes field-for-field, and FastAPI
serializes it with an explicit ``response_model``. A parallel DTO here would
be a second definition of the same shape with nothing to translate.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class ScorePointDTO(BaseModel):
    """A single point in a stock's score/rank history.

    Scores are serialized as strings, not floats: they are exact ``Decimal``
    values in the domain, and a float round-trip would make a displayed score
    disagree with the persisted one.
    """

    run_date: date
    security_id: int
    rank: int | None
    momentum_score: Decimal
    buy_setup_score: Decimal


class StockHistoryDTO(BaseModel):
    """A stock's score/rank history across runs, one point per run date."""

    symbol: str
    score_history: list[ScorePointDTO]
