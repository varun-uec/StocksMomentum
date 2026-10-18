"""Golden tests for alert conditions (FR-22, M15). Fixed bars give fixed firings."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from momentum25.domain.entities.alert import Firing, SeriesPoint, first_firing

D = Decimal


def _points(*values: str | None, partial_last: bool = False) -> list[SeriesPoint]:
    """One point per weekday from Monday 3 August 2026."""
    days = [date(2026, 8, 3 + i) for i in range(5)] + [date(2026, 8, 10 + i) for i in range(5)]
    out = [SeriesPoint(days[i], None if v is None else D(v)) for i, v in enumerate(values)]
    if partial_last:
        out[-1] = SeriesPoint(out[-1].date, out[-1].value, partial=True)
    return out


ARMED = date(2026, 8, 3)  # the alert was created after Monday's bar


@pytest.mark.parametrize(
    ("condition", "values", "expected"),
    [
        # 70 is the threshold throughout.
        ("crosses_above", ("65", "69", "70", "71", "72"), Firing(date(2026, 8, 6), D("71"))),
        ("crosses_above", ("71", "72", "73"), None),  # already above: no cross
        ("crosses_below", ("75", "71", "70", "69"), Firing(date(2026, 8, 6), D("69"))),
        # Monday's bar is not after ARMED, so Tuesday fires.
        ("above", ("71", "72"), Firing(date(2026, 8, 4), D("72"))),
        ("below", ("60", "75", "69.99"), Firing(date(2026, 8, 5), D("69.99"))),
        ("above", ("70", "70"), None),  # equal is not above
    ],
)
def test_each_condition_fires_on_the_first_bar_that_meets_it(
    condition: str, values: tuple[str, ...], expected: Firing | None
) -> None:
    assert first_firing(condition, D("70"), ARMED, _points(*values)) == expected  # type: ignore[arg-type]


def test_a_cross_may_start_on_the_armed_bar() -> None:
    # Monday 69 (armed after it), Tuesday 71: a cross on Tuesday.
    assert first_firing("crosses_above", D("70"), ARMED, _points("69", "71")) == Firing(
        date(2026, 8, 4), D("71")
    )


def test_a_warm_up_gap_never_fires_and_breaks_a_cross() -> None:
    assert first_firing("crosses_above", D("70"), ARMED, _points("65", None, "71", "72")) is None
    after_gap = _points("65", None, "69", "71")
    assert first_firing("crosses_above", D("70"), ARMED, after_gap) == Firing(
        date(2026, 8, 6), D("71")
    )


def test_a_running_week_or_month_never_fires() -> None:
    running = _points("60", "61", "80", partial_last=True)
    assert first_firing("above", D("70"), ARMED, running) is None


def test_the_result_does_not_depend_on_later_bars() -> None:
    """A check run a week late fires on the same bar as one run on the day."""
    on_the_day = first_firing("crosses_above", D("70"), ARMED, _points("65", "71"))
    a_week_late = first_firing(
        "crosses_above", D("70"), ARMED, _points("65", "71", "60", "75", "50", "90")
    )
    assert on_the_day == a_week_late == Firing(date(2026, 8, 4), D("71"))


def test_re_arming_watches_only_later_bars() -> None:
    points = _points("65", "71", "60", "75")
    assert first_firing("crosses_above", D("70"), date(2026, 8, 4), points) == Firing(
        date(2026, 8, 6), D("75")
    )
