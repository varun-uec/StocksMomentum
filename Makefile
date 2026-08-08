# Momentum25 India — developer convenience targets.
# Most workflows run through Docker Compose; backend targets assume `cd backend`.

.PHONY: help up up-dev down logs migrate revision backend-install lint format typecheck test web-install web-dev clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

up: ## Start the full stack (db, redis, api, web)
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

web-dev: ## Run frontend dev server
	cd web && npm run dev

clean: ## Remove volumes and build caches
	docker compose down -v
