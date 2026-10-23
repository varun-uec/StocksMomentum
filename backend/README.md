# Momentum25 India — Backend

Python 3.12 / FastAPI backend. Hexagonal architecture: see
[`docs/current/architecture.md`](../docs/current/architecture.md) for the as-built view and
[`docs/architecture/`](../docs/architecture) for the approved blueprint.

## Layout
```
src/momentum25/
  domain/         pure core — entities, value objects, ports, engine/rule/strategy interfaces
  application/    use cases + DTOs (orchestration)
  infrastructure/ adapters — persistence, redis, providers, scheduler, config, logging
  interface/      adapters — FastAPI app, routers, CLI
  app/services/   daily screening job, bulk market sync
  main.py         ASGI app factory
src/wickstreet/   Wickstreet 2.0 MF app (ADR-022, ADR-023); one package per bounded context
src/platform_common/  logging, database and HTTP middleware shared by both apps
src/apphost/      serves Momentum25 at / and Wickstreet 2.0 at /api/v1/mf in one process
```
The dependency rules are enforced by import-linter (`uv run lint-imports`).

## Local development
```bash
uv sync --all-extras
uv run alembic upgrade head
uv run uvicorn momentum25.main:app --reload
```
Or use Docker Compose from the repo root: `make up`.

To run both apps, set up the Wickstreet 2.0 roles and schema once, then start the host.
`WICKSTREET_ADMIN_DATABASE_URL` must log in as a role that can create roles.
```bash
uv run wickstreet db-roles
uv run alembic -c alembic-wickstreet.ini upgrade head
uv run python -m apphost         # loopback only in personal mode
```

MF data (ADR-023 U10, U11). The owner records each source's grants with the owner login,
then runs the acquisition in this order. Every command is resumable.
```bash
uv run wickstreet rights grant amfi --use automated_retrieval --use storage --basis "..." --by owner
uv run wickstreet mf backfill    # AMFI direct: scheme master, then one run per date
uv run wickstreet mf archive     # TigZig: dates before AMFI's first served date, then fills
uv run wickstreet mf crosscheck  # compare a fixed sample of codes with MFAPI; writes nothing
uv run wickstreet mf refresh     # the 11:30 IST job, run now
uv run wickstreet mf reparse     # after a parser fix: re-derive AMFI dates from kept raw files
uv run wickstreet mf report      # coverage, gaps, anomalies and conflicts as JSON
```

## Quality
```bash
uv run ruff check src tests      # lint
uv run ruff format src tests     # format
uv run mypy src                  # types (strict)
uv run lint-imports              # architecture boundaries
uv run pytest                    # tests
```
