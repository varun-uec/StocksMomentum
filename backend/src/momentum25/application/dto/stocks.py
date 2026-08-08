"""Stock detail, explainability, and history DTOs."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class RuleResultDTO(BaseModel):
    """A single rule's contribution to a stock's score (explainability)."""

    rule_id: str
    label: str
    engine_id: str
    passed: bool
    value: Decimal | None
    threshold: Decimal | None
    operator: str
    weight: Decimal
    contribution: Decimal
    explanation: str


class EngineBreakdownDTO(BaseModel):
    """An engine's score and its contributing rules."""

    engine_id: str
    engine_score: Decimal
    passed_gate: bool
    rules: list[RuleResultDTO]


class ScorePointDTO(BaseModel):
    """A single point in a stock's score/rank history."""

    run_date: date
    rank: int | None
    momentum_score: Decimal
    buy_setup_score: Decimal


class StockExplanationDTO(BaseModel):
    """Full explainability payload for one stock within a run."""

    symbol: str
    name: str
    run_id: int
    run_date: date
    momentum_score: Decimal
    buy_setup_score: Decimal
    hard_filters_passed: bool
    engines: list[EngineBreakdownDTO]
    rationale: str


class StockHistoryDTO(BaseModel):
    """A stock's score/rank history across runs."""

    symbol: str
    points: list[ScorePointDTO]
