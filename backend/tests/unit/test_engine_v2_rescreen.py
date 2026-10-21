"""Hold-out guard of the engine-v2 re-screen driver (Round 6)."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from engine_v2_monthly_rescreen import horizons_before  # noqa: E402

SESSIONS = [date(2022, 1, 3) + timedelta(days=i) for i in range(400)]  # one "session" per day


def test_only_horizons_that_exit_before_the_holdout_are_kept() -> None:
    run = SESSIONS[0]
    holdout_start = SESSIONS[100]  # the 100th session after the run
    assert horizons_before(SESSIONS, run, holdout_start, (5, 60, 99, 100, 101, 252)) == (5, 60, 99)


def test_horizons_not_yet_matured_are_dropped() -> None:
    run = SESSIONS[-10]
    assert horizons_before(SESSIONS, run, date(2100, 1, 1), (5, 10)) == (5,)
