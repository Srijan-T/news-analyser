# Common tasks. Run `make help` to list them.
.PHONY: help install db migrate migration dev dev-backend dev-frontend lint format typecheck test check

help:  ## List available targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

install:  ## Install backend and frontend dependencies
	cd backend && uv sync
	cd frontend && npm install

db:  ## Start local Postgres (port 5433) and wait until it's ready
	docker compose up -d --wait

migrate: db  ## Apply database migrations
	cd backend && uv run alembic upgrade head

migration: db  ## Create a migration from model changes: make migration name="add searches"
	cd backend && uv run alembic revision --autogenerate -m "$(name)"

dev: migrate  ## Run backend (:8000) and frontend (:5173) together
	$(MAKE) -j2 dev-backend dev-frontend

dev-backend:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

lint:  ## Lint backend (ruff) and frontend (oxlint)
	cd backend && uv run ruff check app tests migrations && uv run ruff format --check app tests migrations
	cd frontend && npm run lint

format:  ## Auto-format backend code
	cd backend && uv run ruff format app tests migrations && uv run ruff check --fix app tests migrations

typecheck:  ## Type-check backend (pyright) and frontend (tsc)
	cd backend && uv run pyright
	cd frontend && npx tsc -b

test: db  ## Run backend tests (against the separate test database)
	cd backend && uv run pytest

check: lint typecheck test  ## Everything CI runs
