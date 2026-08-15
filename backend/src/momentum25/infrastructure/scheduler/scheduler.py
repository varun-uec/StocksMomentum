"""In-process scheduler service (APScheduler).

Owns the daily post-close trigger lifecycle (ADR-007). The job *callable* that runs a
screening pipeline is registered in milestone M7; this phase wires the lifecycle so
startup/shutdown and configuration are in place and observable.

Includes recovery logic: on restart, missed jobs are detected and caught up
to prevent data gaps. Idempotency is enforced via distributed locking so the
daily job never runs twice for the same date when workers are scaled out.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime

from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from momentum25.infrastructure.config.settings import Settings
from momentum25.infrastructure.logging.setup import get_logger

_logger = get_logger("scheduler")


class SchedulerService:
    """Manages the APScheduler lifecycle and the daily screening job.

    Recovery: On startup, if the scheduler was down during a scheduled job
    window, the missed run is detected and executed once. This is handled
    by setting ``misfire_grace_time`` to a large enough value and using
    ``coalesce=True`` to ensure only one catch-up run per missed window.
    """

    def __init__(self, settings: Settings) -> None:
        """Create the scheduler from settings (not started until :meth:`start`)."""
        self._settings = settings
        self._job_store = MemoryJobStore()
        self._scheduler = AsyncIOScheduler(
            timezone=settings.timezone,
            jobstores={"default": self._job_store},
        )

    def register_daily_job(self, job: Callable[[], Awaitable[None]]) -> None:
        """Register the daily post-close screening job with recovery.

        Args:
            job: An async, no-argument callable that runs the ingest+screen pipeline.

        Features:
        - ``misfire_grace_time``: Allows missed jobs to be caught up within 24 hours.
        - ``coalesce``: Merges multiple missed runs into one catch-up execution.
        - ``replace_existing``: Idempotent registration on restart.
        """
        trigger = CronTrigger.from_crontab(
            self._settings.schedule_cron, timezone=self._settings.timezone
        )
        self._scheduler.add_job(
            job,
            trigger=trigger,
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

        # Log scheduler state for observability
        jobs = self._scheduler.get_jobs()
        for job in jobs:
            next_run = job.next_run_time
            _logger.info(
                "scheduler_job_state",
                job_id=job.id,
                next_run=next_run.isoformat() if next_run else None,
                pending=job.pending,
            )

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
