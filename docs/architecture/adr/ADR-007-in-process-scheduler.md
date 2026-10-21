# ADR-007: In-process APScheduler, Queue-ready

**Status:** Accepted

## Context
The MVP needs a daily post-close trigger (FR-12) and on-demand runs, deployed locally/self-hosted with minimal infrastructure. Future SaaS scale needs distributed, resilient job execution.

## Decision
Use **APScheduler (AsyncIOScheduler)** running in-process within the API service for MVP scheduling, with the screening pipeline implemented as a plain callable use case (`RunScreening`). The trigger path is abstracted so it can move to a queue/worker (Celery/Arq + Redis) later.

## Consequences
- Zero extra infrastructure for MVP; one container runs API + scheduler.
- Single-host failure pauses scheduling — acceptable for local MVP.
- Migration to a distributed worker is additive (the use case is already I/O-port-driven), no domain change.

## Alternatives considered
- **Celery/Arq + Redis from day one:** rejected for MVP — unnecessary operational overhead.
- **System cron invoking the CLI:** viable, but in-process scheduler keeps config/observability in one place; CLI remains available for manual/cron use.

## Update, 2026-10-21 (R3-B-21)
The scheduler is in-process, as decided. Four facts changed after Round 3:
- The job store is in memory, so a restart forgot missed slots. Startup now runs one catch-up when the latest slot on an exchange session has no run (R3-B-11).
- Cron weekday numbers follow cron (1 = Monday). APScheduler 3 counts from Monday = 0, so `1-5` fired Tuesday to Saturday. The trigger now converts numbers to day names (R3-B-26).
- A Redis lock per day stops two workers from running the job twice. Redis is therefore a required service.
- The compose file sets `restart: unless-stopped`, so the scheduler returns after a crash or reboot (R3-O-02). Scheduler log lines are JSON like all others (R3-B-20).
