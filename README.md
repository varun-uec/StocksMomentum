# Momentum25 India

A deterministic, explainable momentum-stock screener for the Indian (NSE) market — inspired by Mark Minervini's objective Trend Template / SEPA methodology, built as a strategy-agnostic, configurable platform.

> **Status:** Backend, web UI, screening pipeline, research tooling and walk-forward backtest are implemented and tested. Read [State](docs/current/state.md) before relying on any output.

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

Checks — all four must pass. CI runs the first three; run `lint-imports` by hand:

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
- [Approved blueprint](docs/architecture/) — ADD, Implementation Spec, ADR-001 … ADR-010, strategy configs.

## Stack

Python 3.12 + FastAPI · Next.js (TypeScript) · PostgreSQL 16 · Redis · Alembic · Docker Compose.
