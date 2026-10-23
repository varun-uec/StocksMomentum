"""The screening evaluator: an in-memory filter tree over one snapshot (ADR-018).

A filter is ``{"all": [...]}`` or ``{"any": [...]}`` holding conditions and at most
one more level of groups. A condition on an ``NA`` or ``NM`` value is false, for
every comparison including ``!=`` and ``not_in``. ``is_missing`` and
``is_available`` test the state itself. Sorting puts missing values last and ends
with the plan-option id, so equal requests give equal pages.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal, cast

from wickstreet.analytics.domain.fields import BY_ID, INDEX, Field
from wickstreet.analytics.domain.metrics import Missing, Value
from wickstreet.analytics.domain.snapshot import FundRow, Snapshot

MAX_DEPTH = 2
MAX_SORT_KEYS = 5
_COMPARE = frozenset({">", ">=", "<", "<=", "=", "!="})
_STATE = frozenset({"is_available", "is_missing"})
_OPERATORS: dict[str, frozenset[str]] = {
    "number": _COMPARE | {"between"} | _STATE,
    "date": _COMPARE | {"between"} | _STATE,
    "boolean": frozenset({"=", "!="}) | _STATE,
    "enum": frozenset({"in", "not_in"}) | _STATE,
}
_TESTS: dict[str, Callable[[Any, Any], bool]] = {
    ">": lambda v, x: v > x,
    ">=": lambda v, x: v >= x,
    "<": lambda v, x: v < x,
    "<=": lambda v, x: v <= x,
    "=": lambda v, x: v == x,
    "!=": lambda v, x: v != x,
    "between": lambda v, x: (x[0] is None or v >= x[0]) and (x[1] is None or v <= x[1]),
    "in": lambda v, x: v in x,
    "not_in": lambda v, x: v not in x,
    "is_available": lambda v, x: True,
    "is_missing": lambda v, x: False,
}


class FilterError(ValueError):
    """The request names an unknown field, a wrong operator or value, or nests too deep."""

    def __init__(self, path: str, message: str) -> None:
        """Name the bad node."""
        super().__init__(f"{path or 'filter'}: {message}")
        self.path = path
        self.message = message


@dataclass(frozen=True, slots=True)
class Condition:
    """One test of one field."""

    path: str
    field: str
    op: str
    value: Any

    def matches(self, values: Sequence[Value]) -> bool:
        """Apply the test; a missing value passes ``is_missing`` only."""
        value = values[INDEX[self.field]]
        if isinstance(value, Missing):
            return self.op == "is_missing"
        return _TESTS[self.op](value, self.value)


@dataclass(frozen=True, slots=True)
class Group:
    """All or any of its children."""

    kind: Literal["all", "any"]
    children: tuple[Group | Condition, ...]

    def matches(self, values: Sequence[Value]) -> bool:
        """Combine the children."""
        test = all if self.kind == "all" else any
        return test(child.matches(values) for child in self.children)

    def conditions(self) -> list[Condition]:
        """Every condition in tree order."""
        found: list[Condition] = []
        for child in self.children:
            found += child.conditions() if isinstance(child, Group) else [child]
        return found


def parse_filter(tree: Any) -> Group | None:
    """Validate a filter tree; ``None`` matches every fund."""
    if tree is None:
        return None
    node = _node(tree, "", 0)
    return node if isinstance(node, Group) else Group("all", (node,))


def _join(path: str, part: str) -> str:
    return f"{path}.{part}" if path else part


def _node(tree: Any, path: str, depth: int) -> Group | Condition:
    if not isinstance(tree, dict):
        raise FilterError(path, "expected an object")
    if len(tree) == 1 and next(iter(tree)) in ("all", "any"):
        kind = next(iter(tree))
        if depth >= MAX_DEPTH:
            raise FilterError(path, f"groups nest at most {MAX_DEPTH} levels")
        items = tree[kind]
        if not isinstance(items, list) or not items:
            raise FilterError(path, f"{kind!r} needs a non-empty list")
        return Group(
            kind,
            tuple(_node(c, _join(path, f"{kind}[{i}]"), depth + 1) for i, c in enumerate(items)),
        )
    return _condition(tree, path)


def _condition(tree: dict[str, Any], path: str) -> Condition:
    if not set(tree) <= {"field", "op", "value"} or "field" not in tree or "op" not in tree:
        raise FilterError(path, "a condition has 'field', 'op' and 'value' only")
    field = BY_ID.get(tree["field"]) if isinstance(tree["field"], str) else None
    if field is None:
        raise FilterError(path, f"unknown field {tree['field']!r}")
    op = tree["op"]
    if op not in _OPERATORS[field.type]:
        raise FilterError(path, f"operator {op!r} does not apply to {field.type} field {field.id}")
    return Condition(path, field.id, op, _operand(field, op, tree.get("value"), path))


def _scalar(field: Field, value: Any, path: str) -> Any:
    if field.type == "number" and isinstance(value, int | float) and not isinstance(value, bool):
        return value
    if field.type == "boolean" and isinstance(value, bool):
        return value
    if field.type == "date" and isinstance(value, str):
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError:
            pass
    raise FilterError(path, f"{field.id} needs a {field.type} value, not {value!r}")


def _operand(field: Field, op: str, value: Any, path: str) -> Any:
    if op in _STATE:
        if value is not None:
            raise FilterError(path, f"{op} takes no value")
        return None
    if op == "between":
        if not isinstance(value, list) or len(value) != 2 or value == [None, None]:
            raise FilterError(path, "between needs [min, max]; one side may be null")
        return tuple(None if v is None else _scalar(field, v, path) for v in value)
    if op in ("in", "not_in"):
        if not isinstance(value, list) or not value or not all(isinstance(v, str) for v in value):
            raise FilterError(path, f"{op} needs a non-empty list of strings")
        unknown = sorted(set(value) - set(field.values)) if field.values else []
        if unknown:
            raise FilterError(path, f"{field.id} has no value {unknown[0]!r}")
        return frozenset(value)
    return _scalar(field, value, path)


@dataclass(frozen=True, slots=True)
class SortKey:
    """One sort field and direction."""

    field: str
    descending: bool


def parse_sort(keys: Any) -> tuple[SortKey, ...]:
    """Validate ``[{"field": ..., "dir": "asc"|"desc"}, ...]``."""
    if not isinstance(keys, list) or len(keys) > MAX_SORT_KEYS:
        raise FilterError("sort", f"expected a list of at most {MAX_SORT_KEYS} keys")
    parsed: list[SortKey] = []
    for i, key in enumerate(keys):
        path = f"sort[{i}]"
        if not isinstance(key, dict) or key.get("field") not in BY_ID:
            raise FilterError(path, f"unknown field {key!r}")
        if key.get("dir", "asc") not in ("asc", "desc") or not set(key) <= {"field", "dir"}:
            raise FilterError(path, "dir is 'asc' or 'desc'")
        parsed.append(SortKey(key["field"], key.get("dir") == "desc"))
    return tuple(parsed)


def screen(rows: Sequence[FundRow], where: Group | None, sort: Sequence[SortKey]) -> list[FundRow]:
    """Matching rows in sort order; ties and missing values ordered by plan-option id."""
    matched = sorted(
        (r for r in rows if where is None or where.matches(r.values)),
        key=lambda r: r.plan_option_id,
    )
    # Stable sorts, least significant key first; each keeps missing values last.
    for key in reversed(sort):
        index = INDEX[key.field]
        present = [r for r in matched if not isinstance(r.values[index], Missing)]
        missing = [r for r in matched if isinstance(r.values[index], Missing)]
        present.sort(key=lambda r: cast(Any, r.values[index]), reverse=key.descending)
        matched = present + missing
    return matched


def excluded_for_missing(snapshot: Snapshot, where: Group | None) -> list[dict[str, Any]]:
    """For each condition, the funds it excludes because the value is missing, by reason."""
    if where is None:
        return []
    found = []
    for condition in where.conditions():
        if condition.op == "is_missing":
            continue
        reasons = snapshot.missing[condition.field]
        found.append(
            {
                "path": condition.path,
                "field": condition.field,
                "count": sum(reasons.values()),
                "reasons": dict(sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0]))),
            }
        )
    return found


class CursorError(ValueError):
    """The cursor is malformed or belongs to another snapshot or request."""


def fingerprint(where: Any, sort: Any) -> str:
    """SHA-256 of the canonical filter and sort, as sent."""
    body = json.dumps({"filter": where, "sort": sort}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()


def encode_cursor(revision: int, request: str, offset: int) -> str:
    """An opaque cursor pinned to a snapshot revision and a request fingerprint."""
    return base64.urlsafe_b64encode(json.dumps([revision, request, offset]).encode()).decode()


def decode_cursor(cursor: str, request: str) -> tuple[int, int]:
    """Return (revision, offset), or raise if the cursor is not for this request."""
    try:
        revision, sent, offset = json.loads(base64.urlsafe_b64decode(cursor.encode()))
    except (ValueError, TypeError, binascii.Error):
        raise CursorError("cursor is malformed") from None
    if sent != request or not isinstance(revision, int) or not isinstance(offset, int):
        raise CursorError("cursor does not match this request")
    return revision, offset
