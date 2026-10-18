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
```
The dependency rule is enforced by import-linter (`uv run lint-imports`).

## Local development
```bash
uv sync --all-extras
uv run alembic upgrade head
uv run uvicorn momentum25.main:app --reload
```
Or use Docker Compose from the repo root: `make up`.

## Quality
```bash
uv run ruff check src tests      # lint
uv run ruff format src tests     # format
uv run mypy src                  # types (strict)
uv run lint-imports              # architecture boundaries
uv run pytest                    # tests
```
