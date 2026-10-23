"""Custom screen formulas: arithmetic over number fields (doc 20 §5).

A formula such as ``0.6 * cagr_5y_cat_pct + 0.4 * mdd_3y_cat_pct`` may use number
fields, numbers, ``+ - * /``, unary minus and parentheses. Nothing else parses, so
no code runs. A missing input makes the result missing with that input's state and
reason; a zero divisor or a non-finite result is ``NM``.
"""

from __future__ import annotations

import ast
import math
import re
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from typing import cast

from wickstreet.analytics.domain.fields import Field
from wickstreet.analytics.domain.metrics import ZERO_DENOMINATOR, Missing, Value
from wickstreet.analytics.domain.screening import REGISTRY, Columns, FilterError
from wickstreet.analytics.domain.snapshot import FundRow

MAX_FORMULAS = 10
MAX_LENGTH = 500
NOT_FINITE = "not_finite"
_NAME = re.compile(r"[a-z][a-z0-9_]{0,39}")
_OPERATORS: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
}

Formula = Callable[[Sequence[Value]], Value]


def _combine(op: type[ast.operator], left: Value, right: Value) -> Value:
    if isinstance(left, Missing):
        return left
    if isinstance(right, Missing):
        return right
    if op is ast.Div and right == 0:
        return Missing("NM", ZERO_DENOMINATOR)
    result = _OPERATORS[op](float(left), float(right))
    return result if math.isfinite(result) else Missing("NM", NOT_FINITE)


def _build(node: ast.expr, path: str) -> Formula:
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        constant = float(cast(float, node.value))
        return lambda values: constant
    if isinstance(node, ast.Name):
        column = REGISTRY.get(node.id)
        if column is None or column[0].type != "number":
            raise FilterError(path, f"{node.id!r} is not a number field")
        index = column[1]
        return lambda values: values[index]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub | ast.UAdd):
        inner = _build(node.operand, path)
        sign = -1.0 if isinstance(node.op, ast.USub) else 1.0
        return lambda values: v if isinstance(v := inner(values), Missing) else sign * float(v)
    if isinstance(node, ast.BinOp) and type(node.op) in _OPERATORS:
        left, right, op = _build(node.left, path), _build(node.right, path), type(node.op)
        return lambda values: _combine(op, left(values), right(values))
    raise FilterError(path, "only numbers, number fields, + - * / and parentheses are allowed")


def compile_formulas(definitions: Mapping[str, str]) -> dict[str, Formula]:
    """Validate and compile ``{name: expression}``; names must not be field ids."""
    if len(definitions) > MAX_FORMULAS:
        raise FilterError("formulas", f"at most {MAX_FORMULAS} formulas")
    compiled: dict[str, Formula] = {}
    for name, expression in sorted(definitions.items()):
        path = f"formulas.{name}"
        if not _NAME.fullmatch(name) or name in REGISTRY:
            raise FilterError(path, "a formula name is lower-case, new and at most 40 characters")
        if not isinstance(expression, str) or len(expression) > MAX_LENGTH:
            raise FilterError(path, f"an expression is text of at most {MAX_LENGTH} characters")
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError:
            raise FilterError(path, "the expression does not parse") from None
        compiled[name] = _build(tree.body, path)
    return compiled


def with_formulas(
    rows: Sequence[FundRow], definitions: Mapping[str, str]
) -> tuple[Sequence[FundRow], Columns, dict[str, Counter[str]]]:
    """Rows with formula values appended, the columns that name them, and their missing counts."""
    compiled = compile_formulas(definitions)
    if not compiled:
        return rows, REGISTRY, {}
    base = len(REGISTRY)
    columns = dict(REGISTRY)
    for offset, name in enumerate(compiled):
        field = Field(name, name, "Formula", "number", None, definitions[name])
        columns[name] = (field, base + offset)
    formulas = list(compiled.values())
    extended = [
        FundRow(
            r.plan_option_id,
            r.amfi_code,
            r.name,
            (*r.values, *(f(r.values) for f in formulas)),
            r.anchors,
        )
        for r in rows
    ]
    missing: dict[str, Counter[str]] = {name: Counter() for name in compiled}
    for row in extended:
        for offset, name in enumerate(compiled):
            if isinstance(value := row.values[base + offset], Missing):
                missing[name][value.reason] += 1
    return extended, columns, missing
