# Architecture Decision Records

Each ADR follows: **Context · Decision · Consequences · Alternatives considered**. Status: 001–011, 013 (with its two amendments), 014, 021, 022 and 023 **Accepted**, and 017's Wickstreet 2.0 realignment. 012, 015, 016, 018, 019 and 020, and 017's original decision, are **Proposed**. Each ADR may end with a dated update that records what changed after acceptance. The decision text above it is not rewritten.

The [Wickstreet Target Architecture — ADD Amendment A3](../ADD-amendment-A3.md) was **accepted 2026-10-22** after the owner-requested C1 correction. It is an ADD amendment, not an ADR. Its scoped supersession of ADR-010 is effective; the ADR's historical text is preserved. This acceptance does not authorize implementation.

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
| [010](./ADR-010-no-auth-mvp.md) | No auth in local MVP; SaaS seam assumption superseded by A3 |
| [011](./ADR-011-chart-engine.md) | Chart engine: keep lightweight-charts |
| [012](./ADR-012-open-source-self-hosted.md) | Open-source, self-hosted, local by default *(Proposed)* |
| [013](./ADR-013-web-stack-and-chart-data.md) | Web stack, chart data semantics, workspace persistence *(Accepted)* |
| [014](./ADR-014-strategy-studio.md) | Strategy Studio: configured rules, three result classes, sealed hold-out *(Accepted 2026-10-18; section 12, variant-run handoff, accepted and implemented 2026-10-21)* |
| [013a](ADR-013a-alert-amendment.md) | Amendment to 013: editable armed alerts and drawing snapshots *(Accepted 2026-10-19)* |
| [013b](ADR-013b-line-alert-amendment.md) | Amendment to 013: sloped drawing alerts *(Accepted 2026-10-20)* |
| [015](./ADR-015-licence.md) | Licence *(Proposed)* |
| [016](./ADR-016-fundamentals-point-in-time.md) | Company fundamentals, stored by publication time *(Proposed, Wickstreet 2.0)* |
| [017](./ADR-017-funds-etfs-holdings.md) | Mutual funds, ETFs and holdings disclosures *(Proposed, Wickstreet 2.0; MF data-foundation realignment MF-1 to MF-14 accepted 2026-10-23)* |
| [018](./ADR-018-unified-screening.md) | Unified screening in the domain *(Proposed, Wickstreet 2.0)* |
| [019](./ADR-019-portfolio-look-through.md) | Portfolio ledger and look-through exposure *(Proposed, Wickstreet 2.0)* |
| [020](./ADR-020-descriptive-scorecards.md) | Descriptive scorecards, no composite score *(Proposed, Wickstreet 2.0)* |
| [021](./ADR-021-data-supply-policy.md) | Source-neutral data supply *(Accepted 2026-10-23, Wickstreet 2.0)* |
| [022](./ADR-022-multilingual-research-agent.md) | Multilingual research agent: Pydantic AI, tool boundary, hybrid explanations, egress policy *(Accepted 2026-10-23 with corrections; Phase 1 personal mode)* |
| [023](./ADR-023-operating-modes.md) | One core, two operating modes; production-evolvable personal app; enforced tenant ownership *(Accepted 2026-10-23)* |
