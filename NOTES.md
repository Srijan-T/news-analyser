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

## News providers (`backend/app/services/news/`)

- `base.py`: `NormalizedArticle` (our own article shape), `SearchParams`, the `NewsProvider` protocol, and `NewsProviderError` (maps provider failures to 400/429/502).
- `gnews.py`: calls GNews with the key in the `X-Api-Key` header. `normalize()` turns GNews JSON into `NormalizedArticle`. `_get()` maps GNews status codes to our errors.
- `fake.py`: replays `fixtures/gnews_search.json`. Same normalizer, zero quota.
- `__init__.py`: `get_news_provider()` picks one from `NEWS_PROVIDER`. Routes receive it via `Depends(get_news_provider)`, and tests swap it with `app.dependency_overrides[get_news_provider] = ...`.
- Tests for `gnews.py` use `httpx.MockTransport`: no network, and each test can inspect the outgoing request.

## Search flow

`SearchPage` reads `q`, `sort` and `period` from the URL. The form writes them back with `setSearchParams`, and `useQuery` fetches `/api/news/search` whenever they change. Results are cached for 5 minutes (`staleTime`) and never retried, to protect the 100/day quota.

## Production setup

- `create_app(settings)` builds the app from a `Settings` object. Tests pass their own, e.g. `create_app(Settings(static_dir=tmp))`.
- `app/spa.py`: when `STATIC_DIR` is set (in Docker), a catch-all route serves the built files and falls back to `index.html`. It's registered **last**, so API routes win. Unknown `/api/*` paths still return the JSON 404.
- `app/auth.py`: basic-auth ASGI middleware, active only when both `BASIC_AUTH_*` vars are set. `/api/health` is exempt.
- `tests/conftest.py` pins env vars so your local `backend/.env` never changes test behaviour.
- The frontend's `apiFetch` builds URLs from `window.location.origin`. A relative `fetch` breaks when the page was opened via a `user:pass@host` link.

## Adding an endpoint

1. Create or extend `backend/app/routers/<resource>.py` with a pydantic response model.
2. Include the router in `create_app()` if the file is new.
3. Add a test in `backend/tests/` using `TestClient(app)`.
4. Add a typed function to the `api` object in `frontend/src/api/client.ts`, then call it with `useQuery` / `useMutation`.
