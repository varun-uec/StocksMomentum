"""Base contract for a single screening rule."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Protocol, runtime_checkable

from momentum25.domain.engines.base import EvaluationContext
from momentum25.domain.value_objects.results import RuleResult


@runtime_checkable
class Rule(Protocol):
    """A deterministic, explainable rule.

    Attributes:
        rule_id: Stable identifier referenced by strategy configuration.
        engine_id: The engine this rule belongs to.
        label: Human-readable label for UI/explanations.
    """

    rule_id: str
    engine_id: str
    label: str

    def evaluate(
        self, ctx: EvaluationContext, params: dict[str, Any], weight: Decimal
    ) -> RuleResult:
        """Evaluate the rule and return a self-describing :class:`RuleResult`."""
        ...
