"""The screening evaluator (ADR-018): operators, missing values, validation, order, cursor."""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from wickstreet.analytics.domain.fields import FIELDS, INDEX
from wickstreet.analytics.domain.metrics import NO_NAV, Missing, Value
from wickstreet.analytics.domain.screening import (
    CursorError,
    FilterError,
    decode_cursor,
    encode_cursor,
    excluded_for_missing,
    fingerprint,
    parse_filter,
    parse_sort,
    screen,
)
from wickstreet.analytics.domain.snapshot import FundRow, Snapshot

NA = Missing("NA", NO_NAV)
NM = Missing("NM", "gap_in_window")


def row(pid: int, **values: Value) -> FundRow:
    filled = tuple(values.get(f.id, NA) for f in FIELDS)
    return FundRow(pid, str(10000 + pid), f"Fund {pid}", filled, {})


def snapshot(*rows: FundRow) -> Snapshot:
    return Snapshot(1, 7, 1, date(2026, 10, 22), ("amfi",), rows)


def ids(rows: list[FundRow]) -> list[int]:
    return [r.plan_option_id for r in rows]


def run(rows: tuple[FundRow, ...], tree: Any, sort: Any = ()) -> list[int]:
    return ids(screen(rows, parse_filter(tree), parse_sort(list(sort))))


ROWS = (
    row(1, ret_1y=0.10, plan="direct", active=True, last_nav_date="2026-10-22"),
    row(2, ret_1y=0.20, plan="regular", active=False, last_nav_date="2026-01-02"),
    row(3, ret_1y=NM, plan="direct", active=True),
    row(4, plan="direct"),
)


@pytest.mark.parametrize(
    ("condition", "expected"),
    [
        ({"field": "ret_1y", "op": ">", "value": 0.1}, [2]),
        ({"field": "ret_1y", "op": ">=", "value": 0.1}, [1, 2]),
        ({"field": "ret_1y", "op": "<", "value": 0.2}, [1]),
        ({"field": "ret_1y", "op": "<=", "value": 0.2}, [1, 2]),
        ({"field": "ret_1y", "op": "=", "value": 0.1}, [1]),
        ({"field": "ret_1y", "op": "!=", "value": 0.1}, [2]),
        ({"field": "ret_1y", "op": "between", "value": [0.15, None]}, [2]),
        ({"field": "ret_1y", "op": "between", "value": [None, 0.15]}, [1]),
        ({"field": "ret_1y", "op": "is_available"}, [1, 2]),
        ({"field": "ret_1y", "op": "is_missing"}, [3, 4]),
        ({"field": "plan", "op": "in", "value": ["direct"]}, [1, 3, 4]),
        ({"field": "plan", "op": "not_in", "value": ["direct"]}, [2]),
        ({"field": "active", "op": "=", "value": True}, [1, 3]),
        ({"field": "active", "op": "!=", "value": True}, [2]),
        ({"field": "last_nav_date", "op": ">", "value": "2026-06-30"}, [1]),
        ({"field": "last_nav_date", "op": "between", "value": ["2026-01-01", "2026-01-31"]}, [2]),
    ],
)
def test_operators_and_missing_values(condition: dict[str, Any], expected: list[int]) -> None:
    assert run(ROWS, condition) == expected


@pytest.mark.parametrize("missing", [NA, NM])
@pytest.mark.parametrize(
    ("field", "op", "value"),
    [
        ("ret_1y", ">", 0),
        ("ret_1y", ">=", 0),
        ("ret_1y", "<", 0),
        ("ret_1y", "<=", 0),
        ("ret_1y", "=", 0),
        ("ret_1y", "!=", 0),
        ("ret_1y", "between", [None, 1]),
        ("plan", "in", ["direct"]),
        ("plan", "not_in", ["direct"]),
        ("active", "=", True),
        ("active", "!=", True),
        ("since_start", "!=", "2020-01-01"),
        ("ret_1y", "is_available", None),
    ],
)
def test_every_operator_is_false_on_a_missing_value(
    missing: Missing, field: str, op: str, value: Any
) -> None:
    condition = {"field": field, "op": op} | ({} if value is None else {"value": value})
    assert run((row(1, **{field: missing}),), condition) == []
    assert run((row(1, **{field: missing}),), {"field": field, "op": "is_missing"}) == [1]


def test_groups_combine_and_nest_two_levels() -> None:
    tree = {
        "all": [
            {"field": "plan", "op": "in", "value": ["direct"]},
            {
                "any": [
                    {"field": "ret_1y", "op": ">", "value": 0.05},
                    {"field": "ret_1y", "op": "is_missing"},
                ]
            },
        ]
    }
    assert run(ROWS, tree) == [1, 3, 4]
    assert run(ROWS, None) == [1, 2, 3, 4]


@pytest.mark.parametrize(
    ("tree", "path"),
    [
        ({"field": "nope", "op": ">", "value": 1}, ""),
        ({"all": [{"field": "plan", "op": ">", "value": 1}]}, "all[0]"),
        ({"all": [{"any": [{"field": "ret_1y", "op": ">", "value": "x"}]}]}, "all[0].any[0]"),
        ({"all": [{"any": [{"all": [{"field": "ret_1y", "op": "is_missing"}]}]}]}, "all[0].any[0]"),
        ({"all": []}, ""),
        ({"field": "ret_1y", "op": "between", "value": [None, None]}, ""),
        ({"field": "ret_1y", "op": ">", "value": True}, ""),
        ({"field": "plan", "op": "in", "value": ["sideways"]}, ""),
        ({"field": "ret_1y", "op": "is_missing", "value": 1}, ""),
        ({"field": "since_start", "op": ">", "value": "2020-13-01"}, ""),
        ({"field": "ret_1y", "op": ">", "value": 1, "extra": 1}, ""),
        ([], ""),
    ],
)
def test_invalid_filters_name_the_bad_node(tree: Any, path: str) -> None:
    with pytest.raises(FilterError) as error:
        parse_filter(tree)
    assert error.value.path == path


def test_sort_puts_missing_last_and_breaks_ties_by_id() -> None:
    rows = (
        row(5, ret_1y=0.1, cagr_3y=0.3),
        row(2, ret_1y=NM),
        row(3, ret_1y=0.2),
        row(1, ret_1y=0.1, cagr_3y=0.3),
        row(4, ret_1y=0.1, cagr_3y=0.5),
    )
    assert run(rows, None, [{"field": "ret_1y", "dir": "desc"}]) == [3, 1, 4, 5, 2]
    assert run(rows, None, [{"field": "ret_1y"}]) == [1, 4, 5, 3, 2]
    assert run(rows, None, [{"field": "ret_1y"}, {"field": "cagr_3y", "dir": "desc"}]) == [
        4,
        1,
        5,
        3,
        2,
    ]
    with pytest.raises(FilterError):
        parse_sort([{"field": "ret_1y", "dir": "up"}])


def test_excluded_counts_name_the_reasons() -> None:
    snap = snapshot(*ROWS)
    tree = parse_filter(
        {
            "all": [
                {"field": "ret_1y", "op": ">", "value": 0},
                {"field": "ret_1y", "op": "is_missing"},
            ]
        }
    )
    assert excluded_for_missing(snap, tree) == [
        {
            "path": "all[0]",
            "field": "ret_1y",
            "count": 2,
            "reasons": {NO_NAV: 1, "gap_in_window": 1},
        }
    ]


def test_cursor_is_pinned_to_its_request() -> None:
    request = fingerprint({"field": "ret_1y", "op": "is_missing"}, [])
    cursor = encode_cursor(7, request, 50)
    assert decode_cursor(cursor, request) == (7, 50)
    with pytest.raises(CursorError, match="does not match"):
        decode_cursor(cursor, fingerprint(None, []))
    with pytest.raises(CursorError, match="malformed"):
        decode_cursor("!!!", request)


def test_index_covers_every_field() -> None:
    assert [f.id for f in FIELDS] == sorted(INDEX, key=INDEX.__getitem__)
