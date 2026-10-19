# Wickstreet

An open-source, self-hosted market workspace for NSE daily charts. Its engine, **Momentum25**, is a deterministic, explainable momentum-stock screener for the Indian (NSE) market — inspired by Mark Minervini's objective Trend Template / SEPA methodology, built as a strategy-agnostic, configurable platform.

Wickstreet is a working name. The product direction is in [ADD Amendment A1](docs/architecture/ADD-amendment-A1.md).

> **Status:** Backend, web UI, screening pipeline, research tooling and walk-forward backtest are implemented and tested. Read [State](docs/current/state.md) before relying on any output.

## What it does

Ingests NSE EOD data → maintains an eligible universe → computes technical indicators → evaluates every stock through configurable rule engines → produces deterministic **Momentum** and **Buy Setup** scores → ranks the **Top 25** → persists immutable snapshots → **explains every score** (which rules passed and failed, value versus threshold, contribution).

Same inputs produce the same outputs. Every score is reproducible and traceable to the rules that made it.

## Running it

Requires Docker. `make help` lists every target.

```bash
cp .env.example .env
make up                   # db, redis, api — runs migrations on start
```

- App: http://localhost:8000 (the API serves the web app from the same origin)
- API docs: http://localhost:8000/docs
- `make up-dev` also starts Adminer (8080) and RedisInsight (5540).
- Every port listens on `127.0.0.1` only. There is no login, so anyone who can reach the port has full access. To open it to your LAN, set `APP_BIND=0.0.0.0` and add the host name to `M25_ALLOWED_HOSTS` (see [ADR-012](docs/architecture/adr/ADR-012-open-source-self-hosted.md)). Do not expose it to the internet without an authenticating reverse proxy.

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
make e2e-db                           # clone your database to momentum25_e2e
E2E_DATABASE_URL=postgresql+asyncpg://momentum25:momentum25@localhost:5432/momentum25_e2e make web-test
                                      # also runs Playwright against that clone; use your POSTGRES_PORT
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
