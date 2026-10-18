# Momentum25 India — developer convenience targets.
# Most workflows run through Docker Compose; backend targets assume `cd backend`.

.PHONY: help up up-dev down logs migrate revision backend-install api-dev lint format typecheck test web-install web-dev clean e2e-db web-test

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

up: ## Start the full stack (db, redis, api); the app is at http://localhost:8000
	docker compose up --build

up-dev: ## Start full stack + dev tools (adminer, redisinsight)
	docker compose --profile dev up --build

down: ## Stop and remove containers
	docker compose down

logs: ## Tail all logs
	docker compose logs -f

migrate: ## Apply DB migrations inside the api container
	docker compose run --rm api alembic upgrade head

revision: ## Autogenerate a migration: make revision m="message"
	cd backend && alembic revision --autogenerate -m "$(m)"

backend-install: ## Install backend deps locally (uv)
	cd backend && uv sync --all-extras

api-dev: ## Run the API locally on loopback (matches docker-compose)
	cd backend && .venv/bin/uvicorn momentum25.main:app --host 127.0.0.1 --port 8000 --app-dir src --reload

lint: ## Ruff lint
	cd backend && ruff check src tests

format: ## Ruff format
	cd backend && ruff format src tests

typecheck: ## mypy strict
	cd backend && mypy src

test: ## Run backend tests
	cd backend && pytest

web-install: ## Install frontend deps
	cd web && npm install

web-dev: ## Run the web dev server on :5173; it proxies /api to api-dev on :8000
	cd web && npm run dev

clean: ## Remove volumes and build caches
	docker compose down -v

e2e-db: ## Clone the local database to momentum25_e2e for end-to-end tests (replaces an old clone)
	docker compose exec -T db psql -U $${POSTGRES_USER:-momentum25} -d postgres -c "DROP DATABASE IF EXISTS momentum25_e2e;" -c "CREATE DATABASE momentum25_e2e TEMPLATE $${POSTGRES_DB:-momentum25};"

web-test: ## Web unit tests, lint and end-to-end tests (needs `make e2e-db`)
	cd web && npm test && npm run lint && npm run e2e
