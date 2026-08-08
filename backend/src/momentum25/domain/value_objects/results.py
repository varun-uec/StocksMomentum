"""Result value objects: rule, engine, score, ranking, and history points.

These carry the explainability data that is persisted with every run (FR-11).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class RuleResult:
    """Outcome of a single deterministic rule evaluation.

    Always carries enough information to explain itself (NFR-3): the raw value, the
    threshold/operator it was compared against, the weight, and the contribution to
    the engine score, plus a human-readable explanation.
    """

    rule_id: str
    engine_id: str
    passed: bool
    operator: str
    weight: Decimal
    contribution: Decimal
    explanation: str
    raw_value: Decimal | None = None
    threshold: Decimal | None = None


@dataclass(frozen=True, slots=True)
class EngineResult:
    """Aggregated result of one evaluation engine for one security."""

    engine_id: str
    rule_results: tuple[RuleResult, ...]
    engine_score: Decimal
    passed_gate: bool
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StockScore:
    """Combined scores for one security within a run."""

    security_id: int
    momentum_score: Decimal
    buy_setup_score: Decimal
    engine_results: tuple[EngineResult, ...]
    hard_filters_passed: bool


@dataclass(frozen=True, slots=True)
class Ranking:
    """A security's rank within a run (``rank`` is ``None`` if filtered out)."""

    security_id: int
    momentum_score: Decimal
    buy_setup_score: Decimal
    rank: int | None = None


@dataclass(frozen=True, slots=True)
class ScorePoint:
    """A single point in a security's score/rank history across runs."""

    run_date: date
    rank: int | None
    momentum_score: Decimal
    buy_setup_score: Decimal


@dataclass(frozen=True, slots=True)
class UniverseMembership:
    """A security's per-run universe eligibility record (survivorship-bias audit trail)."""

    security_id: int
    eligible: bool
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class SectorStats:
    """Placeholder for peer (sector/industry) relative-strength distributions.

    Populated by the relative-strength engine in a later milestone.
    """

    by_sector: dict[str, list[Decimal]] = field(default_factory=dict)
    by_industry: dict[str, list[Decimal]] = field(default_factory=dict)