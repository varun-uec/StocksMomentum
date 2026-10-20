"""In-process scheduler service (APScheduler, ADR-007).

Owns the daily post-close screening job.

- **Cron.** ``schedule_cron`` is a standard 5-field crontab. Its day-of-week
  numbers follow cron (0 or 7 = Sunday, 1 = Monday). APScheduler 3 reads
  numbers as 0 = Monday, so :func:`crontab_trigger` converts them to day names.
- **In-process stall.** ``misfire_grace_time`` (24 h) and ``coalesce`` run a
  slot that fired late while the process was alive, once.
- **Downtime.** The job store is in memory, so a restart forgets missed slots.
  :meth:`SchedulerService.catch_up` closes that gap at startup: if the latest
  slot on an exchange session has no screening run started at or after it, the
  job runs once now.
- **Duplicates.** The job takes a Redis lock per day, so scaled-out workers do
  not run it twice.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from momentum25.infrastructure.config.settings import Settings
from momentum25.infrastructure.logging.setup import get_logger

_logger = get_logger("scheduler")

_CRON_DAYS = ("sun", "mon", "tue", "wed", "thu", "fri", "sat", "sun")
# How far back to look for the latest slot on a session: covers a long
# holiday run (e.g. Diwali plus a weekend).
_LOOKBACK_DAYS = 14


def _cron_day(token: str) -> str:
    return _CRON_DAYS[int(token)] if token.isdigit() else token


def crontab_trigger(expr: str, timezone: str) -> CronTrigger:
    """Build a trigger from a 5-field crontab with cron's day-of-week numbering.

    ``CronTrigger.from_crontab`` keeps the numbers, and APScheduler 3 counts
    0 = Monday, so ``1-5`` fired Tuesday to Saturday. Numbers become day names
    here (``1-5`` -> ``mon-fri``). Step values (``*/2``) are passed through.
    """
    minute, hour, day, month, dow = expr.split()
    if "/" not in dow:
        dow = ",".join("-".join(_cron_day(p) for p in part.split("-")) for part in dow.split(","))
    return CronTrigger(
        minute=minute, hour=hour, day=day, month=month, day_of_week=dow, timezone=timezone
    )


def missed_slot(
    trigger: CronTrigger,
    now: datetime,
    last_run_started: datetime | None,
    is_session: Callable[[date], bool],
) -> datetime | None:
    """Return the latest slot on a session day if no run started at or after it.

    Slots on weekends and exchange holidays do not count: their data is the
    previous session's, which that session's slot already covered.
    """
    latest: datetime | None = None
    fire = trigger.get_next_fire_time(None, now - timedelta(days=_LOOKBACK_DAYS))
    while fire is not None and fire <= now:
        if is_session(fire.date()):
            latest = fire
        fire = trigger.get_next_fire_time(fire, fire + timedelta(seconds=1))
    if latest is None:
        return None
    if last_run_started is not None and last_run_started >= latest:
        return None
    return latest


class SchedulerService:
    """Manages the APScheduler lifecycle and the daily screening job."""

    def __init__(self, settings: Settings) -> None:
        """Create the scheduler from settings (not started until :meth:`start`)."""
        self._settings = settings
        self._job_store = MemoryJobStore()
        self._scheduler = AsyncIOScheduler(
            timezone=settings.timezone,
            jobstores={"default": self._job_store},
        )
        self._trigger = crontab_trigger(settings.schedule_cron, settings.timezone)
        self._job: Callable[[], Awaitable[None]] | None = None

    def register_daily_job(self, job: Callable[[], Awaitable[None]]) -> None:
        """Register the daily post-close screening job.

        ``misfire_grace_time`` runs a slot that fired up to 24 h late in a live
        process; ``coalesce`` merges several such slots into one run;
        ``replace_existing`` keeps registration idempotent.
        """
        self._job = job
        self._scheduler.add_job(
            job,
            trigger=self._trigger,
            id="daily_screening",
            replace_existing=True,
            misfire_grace_time=86400,  # 24 hours
            coalesce=True,
        )
        _logger.info(
            "scheduler_job_registered",
            cron=self._settings.schedule_cron,
            misfire_grace_seconds=86400,
            coalesce=True,
        )

    def start(self) -> None:
        """Start the scheduler if enabled in settings."""
        if not self._settings.scheduler_enabled:
            _logger.info("scheduler_disabled")
            return
        self._scheduler.start()
        _logger.info("scheduler_started", timezone=self._settings.timezone)

        for job in self._scheduler.get_jobs():
            next_run = job.next_run_time
            _logger.info(
                "scheduler_job_state",
                job_id=job.id,
                next_run=next_run.isoformat() if next_run else None,
                pending=job.pending,
            )

    async def catch_up(
        self,
        last_run_started: Callable[[], Awaitable[datetime | None]],
        is_session: Callable[[date], bool],
        now: datetime | None = None,
    ) -> datetime | None:
        """Run the daily job once now if the process was down for its latest slot.

        Returns the missed slot, or ``None`` when nothing was missed or the
        scheduler is disabled.
        """
        if not self._settings.scheduler_enabled or self._job is None:
            return None
        current = now or datetime.now(ZoneInfo(self._settings.timezone))
        slot = missed_slot(self._trigger, current, await last_run_started(), is_session)
        if slot is None:
            return None
        _logger.warning("scheduler_catch_up", missed_slot=slot.isoformat())
        self._scheduler.add_job(
            self._job, id="daily_screening_catch_up", replace_existing=True, coalesce=True
        )
        return slot

    def shutdown(self) -> None:
        """Stop the scheduler gracefully."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            _logger.info("scheduler_stopped")

    def get_job_count(self) -> int:
        """Return the number of registered jobs."""
        return len(self._scheduler.get_jobs())

    def get_next_run_time(self) -> datetime | None:
        """Return the next scheduled run time, or None if no jobs are scheduled."""
        jobs = self._scheduler.get_jobs()
        if not jobs:
            return None
        # APScheduler does not annotate ``next_run_time``.
        next_run: datetime | None = jobs[0].next_run_time
        return next_run
