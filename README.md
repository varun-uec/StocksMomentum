# Momentum25 India

A deterministic, explainable momentum-stock screener for the Indian (NSE) market — inspired by Mark Minervini's objective Trend Template / SEPA methodology, built as a strategy-agnostic, configurable platform.

> **Phase:** Architecture approved. Implementation has not started (greenfield). See the roadmap below.

## What it does
Ingests NSE EOD data → maintains an eligible universe → computes technical indicators → evaluates every stock through configurable rule engines → produces deterministic **Momentum** and **Buy Setup** scores → ranks the **Top 25** → persists immutable snapshots → **explains every score** (which rules passed/failed, value vs threshold, contribution).

## Architecture documentation
- **[Architecture Design Document (ADD)](docs/architecture/ADD.md)** — requirements, C4 diagrams, domain/data models, engines, workflows, risks.
- **[Implementation Specification](docs/architecture/IMPLEMENTATION_SPEC.md)** — folder structure, DDL, API contracts, interfaces, indicator/rule/scoring specs, error/auth/observability models.
- **[Architecture Decision Records](docs/architecture/adr/)** — ADR-001 … ADR-010.
- **[Reference strategy config](docs/architecture/strategies/minervini_trend_template.json)** — the Minervini strategy as data.

## Key decisions
- **Backend:** Python 3.12 + FastAPI · **Web:** Next.js (TypeScript) · **DB:** PostgreSQL 16 (+optional TimescaleDB)
- **Data (MVP):** NSE EOD Bhavcopy behind a `MarketDataProvider` port
- **Refresh:** daily scheduled + on-demand · **Deployment:** local/self-hosted Docker Compose, SaaS-ready
- **Architecture:** Clean / Hexagonal — pure, deterministic quant core; all I/O behind ports

## Implementation roadmap (high level)
M0 Scaffolding → M1 Ingestion → M2 Indicators → M3 Trend/RS/Scoring → M4 Run+Persistence → M5 REST API → M6 Web UI → M7 Scheduler → M8 More engines + patterns. Details in [ADD §27](docs/architecture/ADD.md#27-implementation-roadmap).
