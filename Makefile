# Momentum25 India — developer convenience targets.
# Most workflows run through Docker Compose; backend targets assume `cd backend`.

.PHONY: help up up-dev down logs migrate revision backend-install api-dev lint format typecheck test web-install web-dev clean e2e-db test-db test-infra-down web-test

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

up: ## Start the full stack (db, redis, api); the app is at http://localhost:8000
	BUILD_ID=$$(git rev-parse HEAD 2>/dev/null) docker compose up --build

up-dev: ## Start full stack + dev tools (adminer, redisinsight)
	BUILD_ID=$$(git rev-parse HEAD 2>/dev/null) docker compose --profile dev up --build

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

e2e-db: ## Start an isolated, memory-capped Postgres with an empty momentum25_e2e database (prints its URL)
	scripts/test-infra.sh up m25-e2e $${E2E_DB_PORT:-65480} 1024 momentum25_e2e

test-db: ## Start an isolated, memory-capped Postgres for the backend suite (prints M25_DATABASE_URL)
	scripts/test-infra.sh up m25-test $${TEST_DB_PORT:-65479} 1024 momentum25_test

test-infra-down: ## Remove the databases started by e2e-db and test-db
	-scripts/test-infra.sh down m25-e2e
	-scripts/test-infra.sh down m25-test

web-test: ## Web unit tests, lint and end-to-end tests (needs an empty, marked E2E database)
	cd web && npm test && npm run lint && E2E_DATABASE_URL=$${E2E_DATABASE_URL:?set E2E_DATABASE_URL to a dedicated *_e2e database} npm run e2e
