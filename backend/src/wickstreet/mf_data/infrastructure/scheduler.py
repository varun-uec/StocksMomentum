"""The 11:30 IST daily refresh slot (ADR-022 §2.12, ADR-017 MF-10).

The job runs in the app's process; no queue or worker. The job store is in memory,
so a restart forgets a missed slot; :func:`refresh_due` lets startup run it once.
The ingestion lock keeps two processes from running it together.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, time
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

IST = ZoneInfo("Asia/Kolkata")
SLOT = time(11, 30)


def refresh_due(now: datetime, completed_today: bool) -> bool:
    """Whether today's slot has passed in IST without a completed refresh."""
    return now.astimezone(IST).time() >= SLOT and not completed_today


class RefreshScheduler:
    """Runs ``job`` daily at 11:30 IST."""

    def __init__(self, job: Callable[[], Awaitable[None]]) -> None:
        """Create the scheduler for ``job``."""
        self._job = job
        self._scheduler = AsyncIOScheduler(timezone=IST)

    def start(self) -> None:
        """Register the daily slot and start."""
        self._scheduler.add_job(
            self._job,
            CronTrigger(hour=SLOT.hour, minute=SLOT.minute, timezone=IST),
            id="mf_daily_refresh",
            coalesce=True,
            max_instances=1,
            misfire_grace_time=6 * 3600,
        )
        self._scheduler.start()

    def run_now(self) -> None:
        """Run the job once, as soon as the loop is free (startup catch-up)."""
        self._scheduler.add_job(self._job, id="mf_refresh_catch_up", max_instances=1)

    def shutdown(self) -> None:
        """Stop without waiting for a running job."""
        self._scheduler.shutdown(wait=False)
