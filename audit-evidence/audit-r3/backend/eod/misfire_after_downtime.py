"""Does the daily job catch up a run missed while the process was down?

ADR-007 and SchedulerService's docstring say a missed run is detected and run
once on restart (misfire_grace_time=86400, coalesce=True). This starts the
production SchedulerService as a restarted process would, with the cron time
two minutes in the past, and records whether the job runs.
"""
import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from momentum25.infrastructure.config.settings import Settings
from momentum25.infrastructure.scheduler.scheduler import SchedulerService


async def main() -> None:
    tz = ZoneInfo("Asia/Kolkata")
    missed = datetime.now(tz) - timedelta(minutes=2)
    settings = Settings(
        scheduler_enabled=True,
        schedule_cron=f"{missed.minute} {missed.hour} * * *",
        timezone="Asia/Kolkata",
    )
    calls: list[datetime] = []

    async def job() -> None:
        calls.append(datetime.now(tz))

    service = SchedulerService(settings)
    service.register_daily_job(job)
    service.start()
    await asyncio.sleep(5)
    print({
        "missed_slot": missed.strftime("%Y-%m-%d %H:%M"),
        "job_ran_after_restart": bool(calls),
        "next_run": service.get_next_run_time().isoformat(),
    })
    service.shutdown()


asyncio.run(main())
