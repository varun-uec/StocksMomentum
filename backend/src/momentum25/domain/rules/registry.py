"""The rule registry — maps ``rule_id`` to a :class:`Rule` implementation.

Adding a rule means adding one class and registering it here (or via the
``@register`` decorator at import time); no other code changes (ADR-005).
"""

from __future__ import annotations

from momentum25.domain.errors import DomainError
from momentum25.domain.rules.base import Rule


class RuleRegistry:
    """An in-memory registry of rules keyed by ``rule_id``."""

    def __init__(self) -> None:
        """Create an empty registry."""
        self._rules: dict[str, Rule] = {}

    def register(self, rule: Rule) -> Rule:
        """Register a rule. Raises if the ``rule_id`` is already taken.

        Usable as a decorator on rule instances/classes that satisfy :class:`Rule`.
        """
        if rule.rule_id in self._rules:
            raise DomainError(f"Duplicate rule_id: {rule.rule_id}")
        self._rules[rule.rule_id] = rule
        return rule

    def get(self, rule_id: str) -> Rule:
        """Return the rule for ``rule_id`` or raise :class:`DomainError`."""
        try:
            return self._rules[rule_id]
        except KeyError as exc:
            raise DomainError(f"Unknown rule_id: {rule_id}") from exc

    def has(self, rule_id: str) -> bool:
        """Return whether ``rule_id`` is registered."""
        return rule_id in self._rules

    def all_ids(self) -> list[str]:
        """Return all registered rule ids in sorted (deterministic) order."""
        return sorted(self._rules)


# Process-wide registry; rule modules register into this at import time.
rule_registry = RuleRegistry()
