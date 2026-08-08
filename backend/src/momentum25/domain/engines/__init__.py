"""Evaluation engine contracts and the concrete (placeholder) engines.

Each engine is a pure function of an :class:`EvaluationContext` plus its
:class:`~momentum25.domain.entities.strategy.EngineConfig`, returning an
:class:`~momentum25.domain.value_objects.results.EngineResult`. Business logic is
deferred; see individual engine docstrings.
"""

from momentum25.domain.engines.base import EvaluationContext, EvaluationEngine

__all__ = ["EvaluationContext", "EvaluationEngine"]
