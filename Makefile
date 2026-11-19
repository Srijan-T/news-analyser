# Common tasks. Run `make help` to list them.
.PHONY: help install dev dev-backend dev-frontend lint format typecheck test check

help:  ## List available targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

install:  ## Install backend and frontend dependencies
	cd backend && uv sync
	cd frontend && npm install

dev:  ## Run backend (:8000) and frontend (:5173) together
	$(MAKE) -j2 dev-backend dev-frontend

dev-backend:
	cd backend && uv run uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

lint:  ## Lint backend (ruff) and frontend (oxlint)
	cd backend && uv run ruff check app tests && uv run ruff format --check app tests
	cd frontend && npm run lint

format:  ## Auto-format backend code
	cd backend && uv run ruff format app tests && uv run ruff check --fix app tests

typecheck:  ## Type-check backend (pyright) and frontend (tsc)
	cd backend && uv run pyright
	cd frontend && npx tsc -b

test:  ## Run backend tests
	cd backend && uv run pytest

check: lint typecheck test  ## Everything CI runs
