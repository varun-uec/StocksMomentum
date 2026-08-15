# Momentum25 India

A deterministic, explainable momentum-stock screener for the Indian (NSE) market — inspired by Mark Minervini's objective Trend Template / SEPA methodology, built as a strategy-agnostic, configurable platform.

> **Status:** Backend, web UI, screening pipeline, and research/validation surfaces are implemented and tested. Read [Known limitations](#known-limitations) before relying on any output.

## What it does

Ingests NSE EOD data → maintains an eligible universe → computes technical indicators → evaluates every stock through configurable rule engines → produces deterministic **Momentum** and **Buy Setup** scores → ranks the **Top 25** → persists immutable snapshots → **explains every score** (which rules passed and failed, value versus threshold, contribution).

Same inputs produce the same outputs. Every score is reproducible and traceable to the rules that made it.

## Running it

Requires Docker. `make help` lists every target.

```bash
cp .env.example .env
make up                   # db, redis, api, web — runs migrations on start
```

- Web UI: http://localhost:3000
- API docs: http://localhost:8000/docs
- `make up-dev` also starts Adminer (8080) and RedisInsight (5540).

Working on the backend without Docker:

```bash
make backend-install      # uv sync --all-extras
make migrate              # alembic upgrade head
make api-dev              # uvicorn on :8000
```

Checks — all four must pass:

```bash
make lint                 # ruff check src tests
make typecheck            # mypy src (strict)
make test                 # pytest
cd backend && .venv/bin/lint-imports   # architecture contracts
```

`make test` needs PostgreSQL. It refuses any database whose name does not end in `_test`.

## Screening pipeline

1. **Ingest** — NSE EOD bhavcopy behind a `MarketDataProvider` port, into `ohlcv_daily`.
2. **Adjust** — corporate actions (splits, bonuses) set each bar's backward adjustment factor. Cash dividends are stored but do not adjust price, by design.
3. **Universe** — liquidity and eligibility gates select the active set. Membership is recorded per run, so backtests carry no survivorship bias.
4. **Indicators** — moving averages, RSI, MACD, ADX, ATR, 52-week range, volume statistics.
5. **Evaluate** — eight engines score each security: `trend_template`, `relative_strength`, `volume_accumulation`, `pattern`, `breakout`, `momentum_quality`, `risk`, `fundamental`. Which engines run, their weights, and their thresholds all come from the strategy config (ADR-005), not from code.
6. **Score and rank** — Momentum and Buy Setup scores, then the Top 25.
7. **Persist** — every run is an immutable snapshot: scores, ranks, and per-rule results (ADR-006).
8. **Forward returns** — once a horizon matures, realized returns are appended for validation. They are never revised.

Runs are triggered on a daily schedule or on demand.

## API

Versioned under `/api/v1`. Full schema at `/docs`.

| Area | Endpoints |
|---|---|
| Health | `/health`, `/health/live`, `/health/ready`, `/health/startup`, `/health/data-freshness` |
| Runs | `GET,POST /runs`, `/runs/latest`, `/runs/{run_id}`, `POST /runs/execute` |
| Rankings | `/rankings/runs/{run_id}`, `/rankings/runs/{run_id}/stocks/{security_id}/explanation` |
| Stocks | `/stocks/{symbol}`, `/stocks/{symbol}/history`, `/stocks/{symbol}/live`, `/stocks/{symbol}/indicators/series`, `/stocks/{symbol}/elliott-wave`, `POST /stocks/{symbol}/chart-patterns` |
| Securities | `/securities`, `/securities/{symbol}/ohlcv` |
| Market | `/market/context`, `/indices/{index_code}/closes` |
| Watchlist | `GET /watchlist`, `/watchlist/detail`, `POST,DELETE /watchlist/{symbol}` |
| Strategies | `/strategies`, `/strategies/{name}` |
| Validation | `/validation/scorecard/{name}`, `/validation/alpha/{name}`, `/validation/rules/{name}`, `/validation/engines/{name}`, `/validation/historical/{name}`, `POST /validation/dashboard` |
| Research | `POST /research/historical/screen`, `POST /research/compare/runs`, `/research/compare/strategies`, `/research/evaluate/{name}`, `/research/contribution/{name}`, `POST /research/experiment/run`, `POST /research/verify/determinism`, `POST /research/corporate-actions/refresh` |

Return-derived metrics report a `measurability` block. When no matured forward return exists, those metrics are `null` and the block says why — an unmeasured metric is never reported as zero.

## Web UI

Next.js (TypeScript). Routes: dashboard (`/`), `/market`, `/watchlist`, `/strategies`, `/validation`, `/analytics`, `/historical`, `/experiment`, per-stock `/stock/[symbol]` with `/analysis` and `/elliott-wave` views, and a `/learn` section covering the methodology, scoring, and rules.

## Research isolation

Elliott Wave analysis, chart-pattern annotations, and the analysis page's target / risk-reward arithmetic are **research surfaces**. None of them feeds the Momentum score, the ranking, the screening gates, or the stop-loss.

Stop-loss output is risk-only: a downside level and the method that produced it. It carries no profit target, R-multiple, or reward estimate.

## Architecture

Strict Hexagonal / Clean Architecture. Dependencies point inward: interface → application → domain, with infrastructure implementing the domain's ports. Two import-linter contracts enforce this in CI.

- `domain` — pure business logic. No I/O, no frameworks.
- `application` — use cases, orchestration, DTOs.
- `infrastructure` — PostgreSQL repositories, Redis caches, NSE clients, scheduler.
- `interface` — FastAPI routers, request/response mapping.

## Documentation

- **[Architecture Design Document (ADD)](docs/architecture/ADD.md)** — requirements, C4 diagrams, domain/data models, engines, workflows, risks.
- **[Implementation Specification](docs/architecture/IMPLEMENTATION_SPEC.md)** — folder structure, DDL, API contracts, interfaces, indicator/rule/scoring specs.
- **[Architecture Decision Records](docs/architecture/adr/)** — ADR-001 … ADR-010.
- **[Strategy configs](docs/architecture/strategies/)** — `minervini_trend_template.json` is the production strategy; the rest are benchmark and experimental variants.

## Stack

Python 3.12 + FastAPI · Next.js (TypeScript) · PostgreSQL 16 · Redis · Alembic · Docker Compose.

## Known limitations

- **Data freshness is operational.** Rankings describe the latest ingested bar, not necessarily the latest session. Check `/health/data-freshness`; it classifies the gap and reports sessions missed.
- **No sector classification.** `securities.sector` is unpopulated, so the market-context sector breadth panel is empty and says why (`no_sector_classification`).
- **Legacy archives keep their original adjustment factors.** The corporate-action refresh updates `ohlcv_daily` only. Re-running the legacy backfill is what re-adjusts `legacy_ohlcv_daily` and `bse_legacy_ohlcv_daily`.
- **Corporate actions start at 2011-01-06.** NSE's free API caps at 20 rows per symbol, so earlier bars are unadjusted and disclosed as such.
- **Several thresholds are editorial, not validated.** Pattern-detector constants, the risk stop-distance cap, Elliott Wave ranking weights, and forward-return tier boundaries are chosen for consistency, not established by walk-forward evidence.
