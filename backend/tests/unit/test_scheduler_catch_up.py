"""Scheduler cron days and startup catch-up (R3-B-11), with a fake clock and lookup."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from momentum25.infrastructure.config.settings import Settings
from momentum25.infrastructure.scheduler.scheduler import (
    SchedulerService,
    crontab_trigger,
    missed_slot,
)

IST = ZoneInfo("Asia/Kolkata")
TRIGGER = crontab_trigger("30 18 * * 1-5", "Asia/Kolkata")
HOLIDAY = date(2026, 10, 20)  # Tuesday, an NSE holiday


def is_session(day: date) -> bool:
    return day.weekday() < 5 and day != HOLIDAY


def at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=IST)


def test_cron_weekdays_mean_monday_to_friday() -> None:
    # Regression: from_crontab read "1-5" as Tuesday-Saturday (APScheduler 0 = Monday).
    fire, days = TRIGGER.get_next_fire_time(None, at(11, 0)), []
    while fire is not None and len(days) < 6:
        days.append(fire.strftime("%a"))
        fire = TRIGGER.get_next_fire_time(fire, fire + timedelta(seconds=1))
    assert days == ["Mon", "Tue", "Wed", "Thu", "Fri", "Mon"]
    sunday = crontab_trigger("0 9 * * 0,6", "Asia/Kolkata")
    first = sunday.get_next_fire_time(None, at(12, 0))
    assert first is not None and first.strftime("%a") == "Sat"


def test_a_slot_missed_while_down_is_caught_up() -> None:
    # Down over Monday 18:30; restarted Monday 21:00; last run started Friday.
    assert missed_slot(TRIGGER, at(19, 21), at(16, 18, 31), is_session) == at(19, 18, 30)


def test_no_catch_up_when_the_slot_already_has_a_run() -> None:
    assert missed_slot(TRIGGER, at(19, 21), at(19, 18, 30), is_session) is None


def test_no_catch_up_before_the_first_slot_of_the_day() -> None:
    # Monday 10:00: the latest slot is Friday 18:30, which already has a run.
    assert missed_slot(TRIGGER, at(19, 10), at(16, 18, 35), is_session) is None


def test_holidays_and_weekends_fall_back_to_the_last_session_slot() -> None:
    # Tuesday 2026-10-20 is a holiday: its 18:30 slot does not count.
    assert missed_slot(TRIGGER, at(20, 22), at(19, 18, 31), is_session) is None
    assert missed_slot(TRIGGER, at(20, 22), at(16, 18, 31), is_session) == at(19, 18, 30)
    # Sunday: the latest counted slot is Friday's.
    assert missed_slot(TRIGGER, at(18, 12), None, is_session) == at(16, 18, 30)


async def test_catch_up_runs_the_job_once_and_only_when_enabled() -> None:
    async def last_started() -> datetime | None:
        return at(16, 18, 31)

    async def job() -> None:
        return None

    disabled = SchedulerService(Settings(scheduler_enabled=False))
    disabled.register_daily_job(job)
    assert await disabled.catch_up(last_started, is_session, now=at(19, 21)) is None

    service = SchedulerService(Settings(scheduler_enabled=True))
    service.register_daily_job(job)
    service.start()
    try:
        assert await service.catch_up(last_started, is_session, now=at(19, 21)) == at(19, 18, 30)
        assert service.get_job_count() == 2  # the daily job plus one catch-up run
    finally:
        service.shutdown()
