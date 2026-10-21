# Architecture Decision Records

Each ADR follows: **Context · Decision · Consequences · Alternatives considered**. Status: 001–011, 013 (with its two amendments) and 014 **Accepted**. 012 and 015 are **Proposed**. Each ADR may end with a dated update that records what changed after acceptance. The decision text above it is not rewritten.

| ADR | Title |
|---|---|
| [001](./ADR-001-hexagonal-architecture.md) | Hexagonal / Clean architecture |
| [002](./ADR-002-python-fastapi-backend.md) | Python 3.12 / FastAPI backend |
| [003](./ADR-003-nse-bhavcopy-provider.md) | NSE Bhavcopy as MVP data provider |
| [004](./ADR-004-postgresql-persistence.md) | PostgreSQL (+ optional TimescaleDB) |
| [005](./ADR-005-strategy-as-config.md) | Strategy as versioned JSON + rule registry |
| [006](./ADR-006-immutable-run-snapshots.md) | Append-only immutable run snapshots |
| [007](./ADR-007-in-process-scheduler.md) | In-process APScheduler, queue-ready |
| [008](./ADR-008-api-first-thin-clients.md) | API-first, thin clients (mobile readiness) |
| [009](./ADR-009-determinism-contract.md) | Determinism contract |
| [010](./ADR-010-no-auth-mvp.md) | No auth in MVP, SaaS seams pre-built |
| [011](./ADR-011-chart-engine.md) | Chart engine: keep lightweight-charts |
| [012](./ADR-012-open-source-self-hosted.md) | Open-source, self-hosted, local by default *(Proposed)* |
| [013](./ADR-013-web-stack-and-chart-data.md) | Web stack, chart data semantics, workspace persistence *(Accepted)* |
| [014](./ADR-014-strategy-studio.md) | Strategy Studio: configured rules, three result classes, sealed hold-out *(Accepted 2026-10-18)* |
| [013a](./ADR-013-alert-amendment.md) | Amendment to 013: editable armed alerts and drawing snapshots *(Accepted 2026-10-19)* |
| [013b](./ADR-013-line-alert-amendment.md) | Amendment to 013: sloped drawing alerts *(Accepted 2026-10-20)* |
| [015](./ADR-015-licence.md) | Licence *(Proposed)* |
