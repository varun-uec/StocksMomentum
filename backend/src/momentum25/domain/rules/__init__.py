"""Rule contracts and the rule registry.

A rule is a pure, independently testable and explainable predicate
(``IMPLEMENTATION_SPEC.md`` §6/§9). Concrete rules are implemented per milestone and
self-register in the :class:`RuleRegistry`.
"""

from momentum25.domain.rules.base import Rule
from momentum25.domain.rules.registry import RuleRegistry, rule_registry

__all__ = ["Rule", "RuleRegistry", "rule_registry"]
