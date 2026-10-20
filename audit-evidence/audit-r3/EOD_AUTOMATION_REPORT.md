# EOD Automation Report — Round 3

Date: 2026-10-20, updated at about 19:30 IST after the first scheduled run. Each link in the chain is stated separately. "Implemented" does not mean "installed", and "installed" does not mean "has run".

## Exact state

| # | Question | Answer | Evidence |
|---|---|---|---|
| 1 | Is scheduling implemented? | **Yes.** `main._run_daily_screening_job` is registered by `SchedulerService` (APScheduler, in-process, ADR-007). Cron `30 18 * * 1-5`, timezone Asia/Kolkata. Holidays are not skipped by the cron; the pipeline sees no new data and reuses the snapshot. `misfire_grace_time` 24 h, `coalesce` true. | `infrastructure/scheduler/scheduler.py`; container log `scheduler_job_registered` |
| 2 | Is an OS-level scheduler installed? | **No.** No LaunchAgent or LaunchDaemon for Momentum25 or Wickstreet in `~/Library/LaunchAgents` or `launchctl list`. No crontab entry. By design: ADR-007 uses the in-process scheduler. | `launchctl list`, `ls ~/Library/LaunchAgents` |
| 3 | Is it enabled? | **Yes, in the running container.** `M25_SCHEDULER_ENABLED=true`, `M25_SCHEDULE_CRON=30 18 * * 1-5`. The code default is `false`. Direct exchange downloads are off. | `docker exec momentum25-api-1 env` |
| 4 | Has a scheduled execution ever occurred? | **YES — one, observed.** Before 2026-10-20 none was provable: all 138 earlier runs say `MANUAL` (R3-B-05). At **18:30:00 IST (13:00:00 UTC) on 2026-10-20 the scheduler fired unattended**: `daily_screening_job_started` at 13:00:00.047, `execute_screening_no_new_bars`, `screening_completed` run **150** (155 passed, 714 skipped, 1,183 failed, 36.95 s), `alerts_evaluated` (0 alerts), job "executed successfully". Run 150's results hash equals run 149's (`8e1a3aed…`, 1,338 rows). It recorded trigger `MANUAL` (R3-B-05) and a new `data_version` `9c90de3657fc` with a null git commit against 149's `8790a000bd4f` at the same data revision 133621 (R3-B-12). Only one scheduled run has occurred, so repeatability is **not** established. | `eod-scheduled-observation.txt`; container log; read-only `screening_runs` and `screening_results` queries |
| 5 | Is new authorised data available? | **Yes, as of the last refresh.** Latest bar 2026-10-19. 2026-10-20 is an NSE holiday per the exchange calendar. Freshness reports `FRESH`, next session 2026-10-21. The 2026-10-20 refresh was a one-off the owner authorised. | `/health/data-freshness`; `data-readiness` report |
| 6 | Do ingestion and downstream processing complete? | **Yes, on the isolated copy** with local fixture CSVs: import, adjustment, screening, alert evaluation. | worker `eod/` |
| 7 | Do failures produce usable diagnostics? | **Mostly.** Failed screens carry a stored error ("Market data changed during screening (manifest revision 155505, current 155508); no result snapshot was saved"). Gaps: the CLI prints raw tracebacks on database errors, and APScheduler log lines are not JSON (R3-B-20). | worker `eod/` |

**What the daily job does.** At 18:30 IST it takes a Redis day lock, then for each production strategy runs the screening pipeline with ingest off. It screens the stored data and reuses the snapshot when nothing changed. Then it evaluates alerts. It never downloads. New data enters only through `momentum25 import-eod` (authorised CSV); the download endpoints answer 409 while downloads are off.

**Authorised source (item 5).** **BLOCKED.** Direct exchange downloads are off and answer 409. No NSE or BSE subscriber agreement is in the repository. The one-off 2026-10-20 refresh rests on the owner's instruction, not on an agreement. Until that changes there is no authorised unattended source, so the job can only re-screen stored data.

**Consequence.** The automation is a *re-screen of stored data*, not a data refresh. If nobody imports a new session's file, tonight's job changes nothing of value. An unattended end-of-day update is therefore **not available** until the owner decides on an authorised, automated data source. This is the licensing gate in the Security report, not a code gap.

## Operational weaknesses found

| ID | Sev | Finding | Status |
|---|---|---|---|
| R3-B-11 | P2 | **No catch-up after downtime.** The job store is `MemoryJobStore`. A job missed while the process was down is not replayed after restart. The scheduler docstring and `production_readiness.md` claimed recovery. Proven by `eod/misfire_after_downtime.py`. | **Fixed in source** `e9ba4ba`: on start, if the latest cron slot on an NSE session day has no run started at or after it, the job runs once. Weekends and holidays are skipped. Unit tests use a fake clock. Docs now match. **Not deployed.** Limit: a slot that only reused an unchanged snapshot writes no run row, so a restart after it repeats that cheap reuse. |
| R3-B-26 | P2 | **New.** APScheduler 3 numbers crontab weekdays from Monday = 0, so `30 18 * * 1-5` fires **Tuesday to Saturday**. Monday's session is screened on Tuesday; Saturday re-screens Friday. The deployed log shows `day_of_week='1-5'` and a Tuesday firing. | **Fixed in source** `e9ba4ba` (weekday names). **Not deployed.** |
| R3-O-02 | P2 | **The container's restart policy is `no`.** After a crash, an OOM kill, a Docker restart or a reboot, the API and its in-process scheduler stay down until someone starts them. I saw this live: the OOM kill at 10:59 UTC left the API down until my manual start. | **Fixed in source** `8253e97`: `restart: unless-stopped`; db and api capped at 2 GB and 2 CPUs, redis at 256 MB; healthchecks kept. Applies on the next `up`. **Not deployed.** |
| R3-B-12 / R3-U-09 | P2 | The container has no git, so runs record `git_commit: null`; on a host the commit moved `data_version` per commit. **Confirmed live:** the 18:30 job wrote run 150, a second snapshot of 2026-10-19 with identical results. | **Fixed in source** `8e5922d`, ADR-014 §10 (market-data identity + engine identity in the hash, build id stored but not hashed, legacy keys kept). The first screen after deploy writes one more schema-2 snapshot, then reuses it. **Owner:** add an `ENGINE_VERSION` constant (Q4). **Not deployed.** |
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

Done: the first scheduled execution was observed (item 4). Remaining: a second, repeated unattended run on the **rebuilt** image (expected 2026-10-21 18:30 IST, Wednesday) to show trigger `SCHEDULED`, the stable `data_version` and the catch-up path. That needs the owner to deploy (`make up`); this audit did not deploy.

## Isolation from the owner's stack

With the new `scripts/test-infra.sh` (named volume, hard memory cap, refuses to start without headroom), the worker ran two rounds of load (real-data restore, a full-universe screen and the backend suite) in capped containers while polling the development API every 2 s: **429 samples, 0 non-200, 0 OOMKilled, restart count 0, maximum latency 0.153 s.** The 18:30 IST job ran during the poll and health stayed 200. Evidence: `backend/isolation/`. The main session's own test database moved to the same script.
