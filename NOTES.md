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

1. Submitting the form (or clicking an example topic in `ExampleTopics.tsx` on the empty page) calls the `create` mutation in `SearchPage`, which sends `POST /api/searches`. The mutation resets whenever the shown search changes, so an old error never hides another search.
2. `services/searches.run_search` looks for an identical search (same `cache_key`) from the last 30 minutes. If there is one, it's returned with **200** and the provider isn't called.
3. Otherwise it takes a per-provider Postgres advisory lock (`pg_advisory_xact_lock`, held until the transaction ends), so concurrent new searches can't all slip under the quota. It then re-checks the cache, checks the quota (`quota_status` sums today's `provider_requests` for the provider since 00:00 UTC; a search with fallbacks uses up to 3), calls the provider, drops repeats (same URL, or the same story under another URL: see `drop_near_duplicates`), upserts the articles by URL, stores the search and its `search_results`, and returns **201**.
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
- Tests: `tests/conftest.py` points `DATABASE_URL` at `news_analyser_test` (or `TEST_DATABASE_URL` in CI) and runs `alembic upgrade head` once per test run. Most tests use the rolled-back `db` fixture. `tests/test_search_concurrency.py` commits for real and truncates its tables afterwards, so the test database must be disposable.
- Production migrations run in the Docker `CMD` (`alembic upgrade head && exec uvicorn ...`), not as a Railway pre-deploy command. Pre-deploy containers couldn't reach `postgres.railway.internal`.
- `/api/health` runs `SELECT 1` and returns 503 `database_unavailable` if Postgres is unreachable. Railway's health check uses it.

## AI analysis (`backend/app/services/ai/`, `services/analyses.py`)

- `base.py`: `AnalysisDraft` (the schema sent to OpenAI: plain types plus an enum, which strict mode supports), `ArticleText`, the `Analyzer` protocol, `AnalysisError`, and `normalize()`. `normalize()` clamps the score, caps the lists, and drops any evidence quote not found in the text.
- `prompts.py`: `SYSTEM_PROMPT`, `build_input()`, `PROMPT_VERSION`. Change the version whenever you change the wording.
- `openai_analyzer.py`: `client.responses.parse(..., text_format=AnalysisDraft)`. `output_parsed is None` means a refusal → `ai_output_invalid`. A pydantic `ValidationError` → `ai_output_invalid`. `openai.APIError` → `ai_unavailable`.
- `fake.py`: keyword-count sentiment for offline dev and tests. `get_analyzer()` in `__init__.py` picks one from `ANALYZER`.
- `services/analyses.analyze_article`: returns the stored analysis if there is one (no AI call). Otherwise it analyzes, stores and commits. A unique-constraint race keeps the first.
- Frontend: `ArticleDetail.tsx` (panel plus analyze mutation), `SentimentBadge.tsx`. The selected article is `?article=` in the URL.

## Batch analysis (`services/batches.py`, `routers/batches.py`, `components/SearchResults.tsx`)

- `create_batch` checks every id exists (404 with `missing_ids` otherwise) and stores one `AnalysisBatchItem` per article, marking already-analyzed ones `skipped`.
- The route schedules `BatchRunner.run` as a FastAPI background task, which runs after the 202 is sent. The runner reads the pending items and processes them with up to `WORKERS = 3` threads. Each thread opens its **own session** (sessions aren't thread-safe), marks the item `running`, calls `analyses.analyze_article` (so the per-article row lock still prevents double AI calls), then marks it `done`/`skipped`/`failed` with the error code.
- Status isn't stored on the batch; it's derived from the items. `item_state()` reports items unfinished for over `STALE_AFTER` (10 min) as `failed`/`interrupted`. The GET never writes.
- Tests override `get_batch_runner` with `workers=1` and the test session (same code, run inline). One test uses the real threaded runner with committed rows.
- Frontend: `SearchResults` holds the checkbox selection and the batch id, polls `GET /api/analysis-batches/{id}` every second until `done`, and patches each finished analysis into the cached search so the cards update live. The batch id is also kept in the query cache (`['active-batch', searchId]`), so leaving the page mid-batch and coming back resumes the progress. When the batch is done it shows a summary toast, re-reads the search and invalidates `article`, `history` and `stats`. Failed items show their reason (`error_code`) on the card.

## Forgiving search (`services/query_fix.py`, `run_search` in `services/searches.py`)

- Only when the first search finds nothing (and `exact` is false), `_fallbacks()` tries the corrector's suggestion, then `broaden()` ("a OR b"). `_ProviderCalls` counts every call into `provider_requests`, stops at the remaining daily budget, and sleeps `NEWS_MIN_REQUEST_INTERVAL` between calls.
- `LocalSpellCorrector.check()` is **confident** only for a distance-1 fix to a common word (≥ 5M uses) that beats the runner-up 10×. These thresholds were calibrated on real cases (see the `test_query_fix.py` parametrize lists). Capitalized words and operators are never touched. `HybridCorrector` asks the LLM only when local is unsure.
- The cache key is what was **typed** (plus `|exact`). The stored `query` is what **ran**, and `original_query` is set only if they differ.
- `GET /api/articles/similar` uses `word_similarity()` from `pg_trgm`; the migration enables the extension. The frontend's `EarlierMatches` shows these when a search finds nothing.
- The fake provider behaves like GNews (no match gives `[]`, and `OR` is supported), so these paths show up in dev.

## History (`services/history.py`, `pages/HistoryPage.tsx`)

- `_conditions(filters)` builds the WHERE clauses over `Article LEFT JOIN Analysis`. Both `list_articles` and `stats` use it, which is why the stats strip always matches the list.
- `stats` groups by sentiment for the counts and averages. `sources` deliberately ignores the filters, so the dropdown keeps all its options.
- Frontend: the filters live in the URL (`?sentiment=&source=&search=&within=&sort=&page=&article=`). `historyQuery()` in `client.ts` turns them into the shared query string, and `within` becomes `published_from` at request time.

## Theming (`src/index.css`, `src/lib/theme.ts`)

- Use **semantic colour classes**, not raw palette ones: `bg-canvas` (page), `bg-surface` (cards, inputs), `bg-subtle`/`bg-subtle-strong`, `border-line`/`border-line-strong`, `text-fg`/`text-soft`/`text-muted`/`text-faint`, `bg-accent` + `text-accent-fg` (primary buttons), `*-danger-*` (errors). Each is a CSS variable with a light value in `:root` and a dark value in `.dark`.
- Use raw colours (with `dark:` variants) only when the colour carries meaning, as `SentimentBadge` does.
- The `ThemeToggle` stores `'light' | 'dark'` in `localStorage['theme']`; no stored value means System. The inline script in `index.html` repeats that logic before first paint, so keep the two in sync.

## UX helpers (frontend)

- **Toasts:** `const toast = useToast(); toast('Saved', 'success')` (from `lib/toast.ts`, provided by `components/ToastProvider.tsx`). They auto-dismiss after 4.5 s, show at most three at once, and are announced by screen readers.
- **Status-aware API calls:** `apiRequest()` returns `{ data, status }`. `createSearch` returns `{ search, cached }` (200 = reused) and `analyzeArticle` returns `{ analysis, created }` (201 = new). The toasts use these.
- **Keyboard:** `useKeyboardShortcuts({ onSlash, onEscape })` in `lib/shortcuts.ts`. It ignores keys while you're typing in a field.
- **Article panel:** `ArticleDetail` takes `onClose` (a Close button, "Back to results" on phones). Below `lg` it renders after the list, so on mount it scrolls itself into view and takes focus, then scrolls again once the article has loaded (the loading placeholder is too short to reach the top of a short page); closing scrolls back to the card (found by `data-article-id`).
- **Page layout:** Search and History show the article column only while `?article=` is set; otherwise the content is centred. Unknown paths render the `NotFound` route in `App.tsx`.
- **Session expiry:** a 401 mid-session calls `noteSessionExpired()` (`lib/session.ts`, from `main.tsx`), so the sign-in page says the session expired; a deliberate Sign out doesn't.

## Adding an endpoint

1. Create or extend `backend/app/routers/<resource>.py` with a pydantic response model.
2. Include the router in `create_app()` if the file is new.
3. Add a test in `backend/tests/` using `TestClient(app)`.
4. Add a typed function to the `api` object in `frontend/src/api/client.ts`, then call it with `useQuery` / `useMutation`.
