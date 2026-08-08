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
