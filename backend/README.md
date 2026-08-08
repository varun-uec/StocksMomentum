# Momentum25 India — Backend

Python 3.12 / FastAPI backend implementing the Clean/Hexagonal architecture described in
[`docs/architecture`](../docs/architecture). This phase delivers the **foundation**: complete
module hierarchy, stable interfaces, persistence, Redis infrastructure, and API contracts.
Business logic (indicators, rules, scoring) is intentionally deferred — see module docstrings.

## Layout
```
src/momentum25/
  domain/         pure core — entities, value objects, ports, engine/rule/strategy interfaces
  application/    use cases + DTOs (orchestration)
  infrastructure/ adapters — persistence, redis, providers, scheduler, config, logging
  interface/      adapters — FastAPI app, routers, CLI
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
