"""Strategy evaluation rules (ADR-014 §5–6, M14): windows, outcomes, statistics."""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from momentum25.domain.research.strategy_evaluation import (
    EvaluationPolicy,
    decision_outcome,
    decision_sessions,
    exit_session,
    holdout_window,
    newey_west_se,
    power_statement,
    research_end,
    research_window,
    summarize,
)


def _weekdays(start: date, end: date) -> list[date]:
    days = (start + timedelta(days=i) for i in range((end - start).days + 1))
    return [d for d in days if d.weekday() < 5]


SESSIONS = _weekdays(date(2016, 8, 8), date(2026, 8, 7))
POLICY = EvaluationPolicy()


def test_the_holdout_is_the_latest_matured_36_month_block() -> None:
    assert holdout_window(SESSIONS, POLICY) == (date(2023, 1, 2), date(2025, 12, 31))


def test_the_window_stays_put_until_36_new_months_mature() -> None:
    # Two more years of data do not move the window: 2026-2028 has not matured.
    longer = _weekdays(date(2016, 8, 8), date(2028, 8, 7))
    assert holdout_window(longer, POLICY) == (date(2023, 1, 2), date(2025, 12, 31))
    # Once the 2026-2028 block's last forward window closes, the next one opens.
    matured = _weekdays(date(2016, 8, 8), date(2029, 7, 1))
    assert holdout_window(matured, POLICY) == (date(2026, 1, 1), date(2028, 12, 29))


def test_an_unmatured_or_uncovered_block_gives_no_window() -> None:
    assert holdout_window(_weekdays(date(2016, 8, 8), date(2026, 3, 1)), POLICY) == (
        date(2020, 1, 1),
        date(2022, 12, 30),
    )
    assert holdout_window(_weekdays(date(2021, 1, 1), date(2026, 8, 7)), POLICY) is None
    assert holdout_window([], POLICY) is None


def test_research_forward_windows_close_before_the_holdout() -> None:
    start = date(2023, 1, 2)
    end = research_end(SESSIONS, start, POLICY.horizon)
    assert end is not None
    last_exit = exit_session(SESSIONS, end, POLICY.horizon)
    assert last_exit is not None and last_exit < start
    later = SESSIONS[SESSIONS.index(end) + 1]
    assert exit_session(SESSIONS, later, POLICY.horizon) == start  # one more would reach it


def test_decisions_are_every_fifth_session() -> None:
    days = decision_sessions(SESSIONS, date(2023, 1, 2), date(2023, 1, 31), 5)
    assert days == [
        date(2023, 1, 2),
        date(2023, 1, 9),
        date(2023, 1, 16),
        date(2023, 1, 23),
        date(2023, 1, 30),
    ]


def test_an_outcome_reports_top_n_qualified_set_and_rank_ic() -> None:
    ranked = [(rank, 0.1 - rank / 100) for rank in range(1, 31)]  # better rank, better return
    outcome = decision_outcome(date(2023, 1, 2), ranked, top_n=25, min_qualified=10)
    assert outcome.qualified == 30 and outcome.top_n == 25
    assert outcome.top_n_excess == pytest.approx(0.1 - 13 / 100)
    assert outcome.rank_ic == pytest.approx(1.0)
    few = decision_outcome(date(2023, 1, 2), ranked[:5], top_n=25, min_qualified=10)
    assert few.rank_ic is None and few.top_n == 5
    flat = decision_outcome(date(2023, 1, 2), [(r, 0.0) for r in range(1, 20)], 25, 10)
    assert flat.rank_ic is None


def test_newey_west_equals_the_iid_error_at_lag_zero_and_widens_with_overlap() -> None:
    values = [float((i // 10) % 2) for i in range(100)]  # runs of ten: overlap
    iid = math.sqrt(sum((v - sum(values) / 100) ** 2 for v in values) / 100 / 100)
    assert newey_west_se(values, 0) == pytest.approx(iid)
    assert newey_west_se(values, 5) > newey_west_se(values, 0)


def test_a_summary_adjusts_for_families_and_states_power() -> None:
    values: list[float | None] = [0.01 + 0.002 * math.sin(i) for i in range(60)]
    one = summarize(values, POLICY, plausible=0.03, tests=1)
    five = summarize(values, POLICY, plausible=0.03, tests=5)
    assert one is not None and five is not None
    assert five.p_adjusted == pytest.approx(min(1.0, one.p * 5))
    assert five.minimum_detectable > one.minimum_detectable
    assert one.ci_low < one.mean < one.ci_high
    assert "underpowered" not in power_statement(one, "Rank IC", POLICY.power)
    noise = [((i * 7919) % 101) / 101 - 0.5 for i in range(60)]
    noisy = summarize(list(noise), POLICY, plausible=0.03)
    assert noisy is not None and not noisy.powered
    assert "underpowered" in power_statement(noisy, "Rank IC", POLICY.power)


def test_too_few_decisions_is_insufficient_data() -> None:
    assert summarize([0.1] * 29 + [None] * 10, POLICY, plausible=0.03) is None
    assert "insufficient data" in power_statement(None, "Rank IC", POLICY.power)


def test_the_research_window_ends_before_the_holdout_or_the_first_block() -> None:
    window = research_window(SESSIONS, POLICY)
    assert window is not None
    assert window[0] == SESSIONS[POLICY.warmup]
    assert window[1] == research_end(SESSIONS, date(2023, 1, 2), POLICY.horizon)
    # No matured block yet: research stops before the first block in the data.
    young = _weekdays(date(2016, 8, 8), date(2020, 6, 30))
    early = research_window(young, POLICY)
    assert early is not None
    last_exit = exit_session(young, early[1], POLICY.horizon)
    assert last_exit is not None and last_exit < date(2020, 1, 1)
    assert research_window(young[:100], POLICY) is None
