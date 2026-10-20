# Wickstreet

A self-hosted market workspace for NSE daily charts using data the operator is authorized to use. Its engine, **Momentum25**, is a deterministic, explainable momentum-stock screener for the Indian (NSE) market — inspired by Mark Minervini's objective Trend Template / SEPA methodology, built as a strategy-agnostic, configurable platform.

Wickstreet is a working name. The product direction is in [ADD Amendment A1](docs/architecture/ADD-amendment-A1.md).

> **Status:** Backend, web UI, screening pipeline, research tooling and walk-forward backtest are implemented and tested. The project licence and Wickstreet name are pending owner decisions; publication remains on hold. Read [State](docs/current/state.md) before relying on any output.

## What it does

Operates on authorized EOD data → maintains an eligible universe → computes technical indicators → evaluates every stock through configurable rule engines → produces deterministic **Momentum** and **Buy Setup** scores → ranks the **Top 25** → persists immutable snapshots → **explains every score** (which rules passed and failed, value versus threshold, contribution).

Same inputs produce the same outputs. Every score is reproducible and traceable to the rules that made it.

## Running it

Requires Docker. `make help` lists every target.

```bash
cp .env.example .env
make up                   # db, redis, api — runs migrations on start
```

- App: http://localhost:8000 (the API serves the web app from the same origin)
- **First run:** the database starts empty. Wickstreet does not download exchange data by default. Import market data you are authorized to use, then screen the stored data:

  ```bash
  cd backend
  set -a
  source ../.env
  set +a
  uv run momentum25 import-eod /path/to/bars.csv --actions /path/to/corporate-actions.csv
  uv run momentum25 import-benchmark /path/to/nifty500.csv
  uv run momentum25 screen
  ```

  EOD CSV columns: `symbol,date,open,high,low,close,volume`; optional columns: `exchange,name,isin,listing_date,prev_close,turnover_value`. Dates use `YYYY-MM-DD`, prices are raw as supplied by the authorized source, and `turnover_value` is needed by the liquidity gate. A benchmark CSV has `index_code,date,close` and one index code per file. Corporate-action CSV columns are `symbol,ex_date,type,ratio`; `raw_subject` is optional. Include the complete price-affecting action history for the imported symbols and date range. Ratios are the multiplier applied to bars before the ex-date; leave the ratio empty for actions that should not adjust prices. Imports are idempotent and do not access the network.

  Direct NSE/BSE downloads remain available only as an explicit operator opt-in with `M25_DIRECT_EXCHANGE_DOWNLOADS_ENABLED=true`. Confirm the source terms and permissions before enabling them. The scheduler is disabled in the sample configuration.
- API docs: http://localhost:8000/docs
- `make up-dev` also starts Adminer (8080) and RedisInsight (5540).
- Every port listens on `127.0.0.1` only. There is no login. An unauthenticated network-exposed Wickstreet instance is not secure: any reachable browser has full read/write access. Keep it loopback-only; if network exposure is required, put an authenticating reverse proxy in front and add the host name to `M25_ALLOWED_HOSTS` (see [ADR-012](docs/architecture/adr/ADR-012-open-source-self-hosted.md)).

Working on the backend without Docker:

```bash
make backend-install      # uv sync --all-extras
make migrate              # alembic upgrade head
make api-dev              # uvicorn on 127.0.0.1:8000
make web-dev              # Vite on :5173, proxies /api to :8000
```

Web checks:

```bash
cd web && npm test && npm run lint   # Vitest, ESLint
make e2e-db                           # isolated, memory-capped Postgres with an empty momentum25_e2e
E2E_DATABASE_URL=postgresql+asyncpg://momentum25:momentum25@127.0.0.1:65480/momentum25_e2e make web-test
                                      # Playwright seeds synthetic fixtures; it refuses a copied or app database
```

Checks — all four must pass, and CI runs all four:

```bash
make lint                 # ruff check src tests
make typecheck            # mypy src (strict)
make test                 # pytest
cd backend && .venv/bin/lint-imports   # architecture contracts
```

`make test` needs PostgreSQL. It refuses any database whose name does not end in `_test`.

## Documentation

Everything lives in [`docs/`](docs/README.md). Start there.

- [Architecture](docs/current/architecture.md) — containers, layers, data stores, drift from the ADD.
- [Design](docs/current/design.md) — screening pipeline, rules and gates, scoring, determinism, walk-forward backtest.
- [Capabilities](docs/current/capabilities.md) — every API endpoint, web page and CLI command.
- [State](docs/current/state.md) — checks, delivery record, research verdicts, open defects, known limitations.
- [Approved blueprint](docs/architecture/) — ADD, Implementation Spec, ADR-001 … ADR-015, strategy configs.

## Stack

Python 3.12 + FastAPI · React 18 + Vite (TypeScript) · PostgreSQL 16 · Redis · Alembic · Docker Compose.

## Credits

Charts are drawn with [TradingView Lightweight Charts™](https://www.tradingview.com/lightweight-charts/), licensed under the Apache License, Version 2.0.

```
TradingView Lightweight Charts™
Copyright (c) 2025 TradingView, Inc. https://www.tradingview.com/
```

Wickstreet is not affiliated with or endorsed by TradingView, Inc.
