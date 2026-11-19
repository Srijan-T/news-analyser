# News Analyser

Search real-time news, get an AI summary and sentiment for any article, and keep a history of analyses.

> Status: scaffold. Features land one pull request at a time (see the commit history).

## Stack

- **Backend:** Python 3.13, FastAPI, managed with [uv](https://docs.astral.sh/uv/)
- **Frontend:** React + TypeScript (Vite), Tailwind CSS, TanStack Query, React Router
- **Database:** PostgreSQL (coming in a later PR)
- **Hosting:** Railway, as one service: FastAPI serves both the API and the built frontend

## Run locally

Prerequisites: `uv`, Node 20+.

```bash
make install
cp backend/.env.example backend/.env
make dev
```

- App: http://localhost:5173 (Vite forwards `/api` requests to the backend)
- API docs: http://localhost:8000/docs

## Checks

```bash
make check   # lint + typecheck + tests
```

## API conventions

Every error response uses one shape:

```json
{ "error": { "code": "validation_error", "message": "Request validation failed", "details": [...] } }
```

## Decisions and tradeoffs

_To be written as features land._
