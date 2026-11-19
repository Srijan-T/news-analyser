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

1. Submitting the form calls the `create` mutation in `SearchPage`, which sends `POST /api/searches`.
2. `services/searches.run_search` looks for an identical search (same `cache_key`) from the last 30 minutes. If there is one, it's returned with **200** and the provider isn't called.
3. Otherwise it takes a per-provider Postgres advisory lock (`pg_advisory_xact_lock`, held until the transaction ends), so concurrent new searches can't all slip under the quota. It then re-checks the cache, checks the quota (`quota_status` counts today's `searches` rows for the provider since 00:00 UTC), calls the provider, upserts the articles by URL, stores the search and its `search_results`, and returns **201**.
4. The frontend puts the id in the URL (`?search=42`). Refresh, back/forward and the Recent searches links all go through `GET /api/searches/{id}`, which reads stored rows and never calls the provider.
5. New searches are never auto-retried, since a retry could spend quota. After each search the `['searches']` and `['quota']` queries are invalidated so the history and the badge refresh.

Tests: the `db` fixture in `tests/conftest.py` wraps each test in a transaction that's rolled back. `make_client` in `test_searches_api.py` builds an app whose `get_db` and `get_news_provider` are overridden with that session and a recording fake provider.

## Production setup

- `create_app(settings)` builds the app from a `Settings` object. Tests pass their own, e.g. `create_app(Settings(static_dir=tmp))`.
- `app/spa.py`: when `STATIC_DIR` is set (in Docker), a catch-all route serves the built files and falls back to `index.html`. It's registered **last**, so API routes win. Unknown `/api/*` paths still return the JSON 404.
- `app/auth.py` + `app/routers/auth.py`: password sign-in, active only when `APP_PASSWORD` is set (it also needs `SESSION_SECRET`, or startup fails).
  - `POST /api/auth/login` sets an HttpOnly cookie `"<expiry>.<HMAC-SHA256(expiry)>"`. Nothing is stored server-side; `verify_session` just recomputes the signature.
  - `SessionAuthMiddleware` returns 401 `unauthenticated` for `/api/*` without a valid cookie, except health and the auth endpoints. Pages stay open so React can render the form.
  - Frontend: `AuthGate` (in `components/AuthGate.tsx`) reads `GET /api/auth/session`. The `onError` handler in `main.tsx` re-checks the session whenever any request gets `unauthenticated`.
  - Why not HTTP basic auth? Many browsers (embedded ones, link previews, Chrome after a cancel) never show its pop-up, so users got raw JSON.
- `tests/conftest.py` pins env vars so your local `backend/.env` never changes test behaviour.
- The frontend's `apiFetch` builds URLs from `window.location.origin`. A relative `fetch` breaks when the page was opened via a `user:pass@host` link.

## Database (`backend/app/db.py`, `backend/migrations/`)

- `create_app` builds an engine from `settings.database_url` and stores a session factory on `app.state`. Routes take `db: Session = Depends(get_db)`, which gives one session per request and always closes it.
- `Base` (in `db.py`) has a naming convention so constraints get predictable names in migrations.
- Models live in `app/models.py`, which is imported by `migrations/env.py` so autogenerate sees every table. Workflow: edit models → `make migration name="..."` → **read the generated file** → `make migrate`.
- The folder is `migrations/`, not `alembic/`, so it can't shadow the `alembic` package.
- Tests: `tests/conftest.py` points `DATABASE_URL` at `news_analyser_test` (or `TEST_DATABASE_URL` in CI) and runs `alembic upgrade head` once per test run.
- Production migrations run in the Docker `CMD` (`alembic upgrade head && exec uvicorn ...`), not as a Railway pre-deploy command. Pre-deploy containers couldn't reach `postgres.railway.internal`.
- `/api/health` runs `SELECT 1` and returns 503 `database_unavailable` if Postgres is unreachable. Railway's health check uses it.

## AI analysis (`backend/app/services/ai/`, `services/analyses.py`)

- `base.py`: `AnalysisDraft` (the schema sent to OpenAI: plain types plus an enum, which strict mode supports), `ArticleText`, the `Analyzer` protocol, `AnalysisError`, and `normalize()`. `normalize()` clamps the score, caps the lists, and drops any evidence quote not found in the text.
- `prompts.py`: `SYSTEM_PROMPT`, `build_input()`, `PROMPT_VERSION`. Change the version whenever you change the wording.
- `openai_analyzer.py`: `client.responses.parse(..., text_format=AnalysisDraft)`. `output_parsed is None` means a refusal → `ai_output_invalid`. A pydantic `ValidationError` → `ai_output_invalid`. `openai.APIError` → `ai_unavailable`.
- `fake.py`: keyword-count sentiment for offline dev and tests. `get_analyzer()` in `__init__.py` picks one from `ANALYZER`.
- `services/analyses.analyze_article`: returns the stored analysis if there is one (no AI call). Otherwise it analyzes, stores and commits. A unique-constraint race keeps the first.
- Frontend: `ArticleDetail.tsx` (panel plus analyze mutation), `SentimentBadge.tsx`. The selected article is `?article=` in the URL.

## History (`services/history.py`, `pages/HistoryPage.tsx`)

- `_conditions(filters)` builds the WHERE clauses over `Article LEFT JOIN Analysis`. Both `list_articles` and `stats` use it, which is why the stats strip always matches the list.
- `stats` groups by sentiment for the counts and averages. `sources` deliberately ignores the filters, so the dropdown keeps all its options.
- Frontend: the filters live in the URL (`?sentiment=&source=&search=&within=&sort=&page=&article=`). `historyQuery()` in `client.ts` turns them into the shared query string, and `within` becomes `published_from` at request time.

## Adding an endpoint

1. Create or extend `backend/app/routers/<resource>.py` with a pydantic response model.
2. Include the router in `create_app()` if the file is new.
3. Add a test in `backend/tests/` using `TestClient(app)`.
4. Add a typed function to the `api` object in `frontend/src/api/client.ts`, then call it with `useQuery` / `useMutation`.
