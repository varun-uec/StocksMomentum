# EOD Automation Report — Round 3

Date: 2026-10-20, written at about 17:15 IST. Each link in the chain is stated separately. "Implemented" does not mean "installed", and "installed" does not mean "has run".

## Exact state

| # | Question | Answer | Evidence |
|---|---|---|---|
| 1 | Is scheduling implemented? | **Yes.** `main._run_daily_screening_job` is registered by `SchedulerService` (APScheduler, in-process, ADR-007). Cron `30 18 * * 1-5`, timezone Asia/Kolkata. Holidays are not skipped by the cron; the pipeline sees no new data and reuses the snapshot. `misfire_grace_time` 24 h, `coalesce` true. | `infrastructure/scheduler/scheduler.py`; container log `scheduler_job_registered` |
| 2 | Is an OS-level scheduler installed? | **No.** No LaunchAgent or LaunchDaemon for Momentum25 or Wickstreet in `~/Library/LaunchAgents` or `launchctl list`. No crontab entry. By design: ADR-007 uses the in-process scheduler. | `launchctl list`, `ls ~/Library/LaunchAgents` |
| 3 | Is it enabled? | **Yes, in the running container.** `M25_SCHEDULER_ENABLED=true`, `M25_SCHEDULE_CRON=30 18 * * 1-5`. The code default is `false`. Direct exchange downloads are off. | `docker exec momentum25-api-1 env` |
| 4 | Has a scheduled execution ever occurred? | **NOT VERIFIED — no evidence of one.** All 138 stored runs are labelled `MANUAL`, because the trigger was hard-coded to `MANUAL` (R3-B-05, fixed in `dab5b56`, not deployed). No Redis day-lock key exists. The container was created 2026-10-20 10:30 UTC; the scheduler registered at 11:00 UTC (the container was OOM-killed at 10:59 UTC and restarted by me). The next run is 2026-10-20 18:30 IST. | worker `api-container-scheduler-log-extract.txt`; `eod-scheduled-observation.txt` if present |
| 5 | Is new authorised data available? | **Yes, as of the last refresh.** Latest bar 2026-10-19. 2026-10-20 is an NSE holiday per the exchange calendar. Freshness reports `FRESH`, next session 2026-10-21. The 2026-10-20 refresh was a one-off the owner authorised. | `/health/data-freshness`; `data-readiness` report |
| 6 | Do ingestion and downstream processing complete? | **Yes, on the isolated copy** with local fixture CSVs: import, adjustment, screening, alert evaluation. | worker `eod/` |
| 7 | Do failures produce usable diagnostics? | **Mostly.** Failed screens carry a stored error ("Market data changed during screening (manifest revision 155505, current 155508); no result snapshot was saved"). Gaps: the CLI prints raw tracebacks on database errors, and APScheduler log lines are not JSON (R3-B-20). | worker `eod/` |

**What the daily job does.** At 18:30 IST it takes a Redis day lock, then for each production strategy runs the screening pipeline with ingest off. It screens the stored data and reuses the snapshot when nothing changed. Then it evaluates alerts. It never downloads. New data enters only through `momentum25 import-eod` (authorised CSV); the download endpoints answer 409 while downloads are off.

**Consequence.** The automation is a *re-screen of stored data*, not a data refresh. If nobody imports a new session's file, tonight's job changes nothing of value. An unattended end-of-day update is therefore **not available** until the owner decides on an authorised, automated data source. This is the licensing gate in the Security report, not a code gap.

## Operational weaknesses found

| ID | Sev | Finding | Status |
|---|---|---|---|
| R3-B-11 | P2 | **No catch-up after downtime.** The job store is `MemoryJobStore`. A job missed while the process was down is not replayed after restart. The scheduler docstring and `production_readiness.md` claim recovery. Proven by `eod/misfire_after_downtime.py`. | Open |
| R3-O-02 | P2 | **The container's restart policy is `no`.** After a crash, an OOM kill, a Docker restart or a reboot, the API and its in-process scheduler stay down until someone starts them. Together with R3-B-11 a sleeping or restarted Mac skips the day with no trace. I saw this live: the OOM kill at 10:59 UTC left the API down until my manual start. | Open. Fix: `restart: unless-stopped` in compose, and a persistent job store or a catch-up on start. |
| R3-B-12 / R3-U-09 | P2 | The container has no git, so runs record `git_commit: null`; on a host the commit moves `data_version` per commit. **Tonight's job will write a second snapshot of 2026-10-19** next to run #149, because its manifest differs. Both are valid immutable runs; the latest-run pointer will move to the new one. | Open. Owner decision (ADR-014 §7). |
| R3-B-05 | P2 | Scheduled runs were stored as `MANUAL`. | Fixed `dab5b56`. **Not deployed.** |
| R3-B-02 | P1 | **One holiday, weekend or future row in `import-eod` became the latest date.** The next screen produced run 162 COMPLETED with 1 scored name and 1,853 dropped, and `/runs/latest` served that empty run. | Fixed `9a32526`. **Not deployed.** |
| R3-B-03 | P2 | CLI and API returned another run's id (newest completed by date) instead of the run just written. | Fixed `f3e9110` |
| R3-B-04 | P2 | Two identical concurrent screens returned HTTP 500 instead of 409. | Fixed `45bbd83` |
| R3-B-15 | P2 | Migrations, ORM and the development database disagree (`alembic check` reports about 45 operations; the dev database lacks the `(run_id, rank)` index). Tests build the schema with `create_all`, so they do not see it. | Open |

## Failure and recovery matrix

Run by the worker on a restored copy on port 65450 with local fixture CSVs. No network.

| Scenario | Result |
|---|---|
| Missing or delayed source file | Nothing is imported; freshness reports the gap. No empty run. |
| Holiday, weekend or future-dated row | Was accepted and collapsed the screen (R3-B-02). Now rejected. |
| Duplicate session (same file twice) | Idempotent. Revision unchanged. |
| Corrected historical file | New data version, new run. The old run is unchanged. |
| Invalid OHLCV rows | Rejected before any write. |
| Missed job after downtime | **Not caught up** (R3-B-11). |
| Concurrent refresh attempts | One 200 and one 409 (after R3-B-04). |
| Data changed during a screen | Run FAILED with a clear message, 0 rows stored. Retry COMPLETED. |
| Database failure mid-transaction (result write) | Run FAILED, 0 partial rows. Retry reused the failed run id and COMPLETED. |
| Database failure mid-import (second symbol) | Full rollback, RELIANCE unchanged, retry imported both. |
| Backup and restore | `pg_dump -Fc`, 687 MB. `pg_restore` in 14 s. Row counts and `hashtext` row checksums equal the live database on 14 tables (ohlcv 3,206,035; rule_results 5,272,526; and others). |
| Publication consistency | A run stores its manifest (revision, indicator version, registry, git commit, calendar). Gaps are R3-B-05 and R3-B-12. |
| Historical immutability | The repository refuses to update a COMPLETED run and the orchestrator refuses to adopt one. **No database trigger guards the tables**, so SQL can still rewrite them. |

R2-LIMIT-02 (mid-transaction failure, backup and restore) is closed. Not done: killing the process mid-import (the transaction makes it equivalent to the injected failure), raw malformed HTTP headers, multi-hour endurance.

## Incident during this audit

At 10:59 UTC the owner's API container was OOM-killed. The audit's first Postgres copy used tmpfs (RAM) inside the 8 GB Docker VM and filled it (R3-B-25, closed). I restarted `momentum25-api-1`. Health was `ok`; the development database was untouched and healthy throughout. The audit's second copy used a named volume with `--memory 2g`. The API container has **no memory limit**, which is why the kill hit it rather than the copy.

## Verification still pending

The first observable scheduled execution is 2026-10-20 18:30 IST. A background watcher records the container log and the `screening_runs` table (read-only) after 18:40 IST in `audit-evidence/audit-r3/eod-scheduled-observation.txt`. Until that file exists and shows a `daily_screening` execution, item 4 stays **NOT VERIFIED**. Expect the old image to label that run `MANUAL` and to write a duplicate 2026-10-19 snapshot (R3-B-05, R3-B-12).
