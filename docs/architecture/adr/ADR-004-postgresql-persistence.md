# ADR-004: PostgreSQL (+ optional TimescaleDB)

**Status:** Accepted

## Context
We persist relational entities (securities, strategies, runs, results, per-rule explanations) **and** time-series prices (`ohlcv_daily`). We need transactional integrity, append-only snapshot history, and a path to scale time-series volume.

## Decision
Use **PostgreSQL 16** as the single datastore. Enable **TimescaleDB** as an optional hypertable for `ohlcv_daily` behind a config flag; a plain table suffices at MVP scale.

## Consequences
- One operational dependency for MVP; strong integrity + JSONB for strategy config/stats.
- Time-series scaling path (Timescale) available without schema redesign.
- TimescaleDB optionality keeps local self-hosting simple.

## Alternatives considered
- **Pure time-series DB (InfluxDB/Timescale-only):** rejected — relational needs (FKs, joins, snapshots) dominate.
- **SQLite:** rejected — insufficient concurrency and a poor fit for the eventual multi-tenant SaaS.
