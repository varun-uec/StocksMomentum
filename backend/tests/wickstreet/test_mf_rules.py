"""Pure MF rules: blocking checks, anomaly flags (MF-8) and the 11:30 IST slot."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal

import pytest

from wickstreet.mf_data.domain.model import Anomaly, NavRecord
from wickstreet.mf_data.domain.validation import BlockingError, check_nav_day, flag_anomalies
from wickstreet.mf_data.infrastructure.scheduler import IST, refresh_due

DAY = date(2026, 10, 1)


def _nav(code: str, value: str | None, day: date = DAY) -> NavRecord:
    return NavRecord(
        amfi_code=code,
        nav_date=day,
        nav=None if value is None else Decimal(value),
        amc="Example Mutual Fund",
        category="Open Ended Schemes ( X )",
        nav_name=f"Fund {code}",
        plan=None,
        option=None,
        isin_growth=None,
        isin_reinvest=None,
    )


def test_identical_repeats_are_dropped() -> None:
    assert check_nav_day([_nav("1", "10"), _nav("1", "10"), _nav("2", "5")], DAY) == [
        _nav("1", "10"),
        _nav("2", "5"),
    ]


@pytest.mark.parametrize(
    "records",
    [
        [],
        [_nav("1", "10"), replace(_nav("1", "10"), nav=Decimal("11"))],
        [_nav("1", "10", date(2026, 10, 2))],
    ],
    ids=["empty", "conflicting-duplicate", "other-date"],
)
def test_a_blocking_problem_fails_the_file(records: list[NavRecord]) -> None:
    with pytest.raises(BlockingError):
        check_nav_day(records, DAY)


def test_anomalies_are_flagged_not_dropped() -> None:
    records = [
        _nav("missing", None),
        _nav("zero", "0"),
        _nav("negative", "-1"),
        _nav("jump", "13"),
        _nav("steady", "10.5"),
        _nav("new", "99"),
    ]
    previous = {"jump": Decimal("10"), "steady": Decimal("10")}
    assert flag_anomalies(records, previous, Decimal("0.25")) == {
        "missing": Anomaly.MISSING,
        "zero": Anomaly.ZERO,
        "negative": Anomaly.NEGATIVE,
        "jump": Anomaly.JUMP,
    }


@pytest.mark.parametrize(
    ("clock", "completed", "due"),
    [
        ("11:29", False, False),
        ("11:30", False, True),
        ("18:00", False, True),
        ("18:00", True, False),
    ],
)
def test_the_refresh_is_due_after_1130_ist_until_it_completes(
    clock: str, completed: bool, due: bool
) -> None:
    hour, minute = map(int, clock.split(":"))
    now = datetime(2026, 10, 23, hour, minute, tzinfo=IST)
    assert refresh_due(now, completed) is due
