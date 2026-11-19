# Codebase notes

A walkthrough of how the code fits together, for working on it without AI help.

## Layout

```
backend/
  app/main.py          create_app(): builds the FastAPI app, registers error handlers and routers
  app/config.py        Settings read from environment variables (and backend/.env locally)
  app/errors.py        AppError + handlers that turn every failure into {"error": {...}}
  app/routers/         one file per resource; each exposes `router`, mounted under /api
  tests/               pytest; TestClient calls the app in-process (no server needed)
frontend/
  src/main.tsx         React root: TanStack Query provider + React Router
  src/App.tsx          header/nav + route table
  src/api/client.ts    apiFetch(): the only place that calls fetch; throws ApiError
  src/pages/           one component per route
  src/components/      reusable pieces
```

## Request flow

1. A browser request to `/api/...` goes to Vite (port 5173) in dev, which proxies it to FastAPI (port 8000).
2. FastAPI matches a router, validates inputs with pydantic, and returns a pydantic model as JSON.
3. On failure, raise `AppError(status, code, message)`. `errors.py` renders it in the standard envelope. Validation errors (422), unknown routes (404) and unexpected crashes (500) are wrapped the same way.
4. On the frontend, `apiFetch` parses the envelope into an `ApiError`, so components can switch on `error.code`.

## Adding an endpoint

1. Create or extend `backend/app/routers/<resource>.py` with a pydantic response model.
2. Include the router in `create_app()` if the file is new.
3. Add a test in `backend/tests/` using `TestClient(app)`.
4. Add a typed function to the `api` object in `frontend/src/api/client.ts`, then call it with `useQuery` / `useMutation`.
