# News Analyser

Search real-time news, get an AI summary and sentiment for any article, and keep a history of analyses.

> Status: scaffold. Features land one pull request at a time (see the commit history).

## Stack

- **Backend:** Python 3.13, FastAPI, managed with [uv](https://docs.astral.sh/uv/)
- **Frontend:** React + TypeScript (Vite), Tailwind CSS, TanStack Query, React Router
- **Database:** PostgreSQL 17 with SQLAlchemy 2.0 and Alembic migrations
- **Hosting:** Railway, as one service: FastAPI serves both the API and the built frontend

## Run locally

Prerequisites: `uv`, Node 22.22+ (React Router 8 requires it), Docker (for Postgres).

```bash
make install
cp backend/.env.example backend/.env
make dev     # starts Postgres (port 5433), applies migrations, runs backend + frontend
```

- App: http://localhost:5173 (Vite forwards `/api` requests to the backend)
- API docs: http://localhost:8000/docs

By default the backend uses `NEWS_PROVIDER=fake`, which replays a saved GNews response, so local development spends none of the API quota. For live news, set `NEWS_PROVIDER=gnews` and `GNEWS_API_KEY` in `backend/.env`.

## News source

[GNews](https://gnews.io): its free plan gives keyword search, 100 requests/day, articles about 12 hours behind real time, and a ~250-character snippet per article. The UI says so next to the results.

I first evaluated **FreeNewsAPI.io**, which advertises real-time articles and full article text. A live probe showed that its keyword search had been removed (`q` returns "Search using the 'q' field has been removed."), and its title search returned HTTP 500. Since searching is the core of the brief, I rejected it. Providers sit behind a `NewsProvider` interface, so adding a full-text source later is one new class.

## Database

- `make db` starts Postgres in Docker on port **5433**, so it doesn't clash with a local install on 5432. It creates two databases: `news_analyser` for dev and `news_analyser_test` for tests.
- `make migrate` applies migrations. `make migration name="..."` generates one from model changes.
- Tests migrate the test database to the latest version at the start of each run, which also checks that every migration applies cleanly.
- In production, the container runs `alembic upgrade head` before starting the server. If a migration fails, the server never starts, the health check fails, and Railway keeps the previous deploy serving. This isn't a Railway pre-deploy command because Railway's private network (where Postgres lives) is only guaranteed at runtime.

## Checks

```bash
make check   # lint + typecheck + tests
```

CI (GitHub Actions) runs the same checks on every pull request, plus a production Docker build. It uses the fake news provider, so it needs no secrets and spends no API quota.

## Deployment

One Docker image (see [`Dockerfile`](Dockerfile)) runs the whole app. A Node stage builds the React frontend, and FastAPI serves it alongside `/api` on a single origin, so there's no CORS. The app is deployed on Railway, which builds the root `Dockerfile` on every push to `main`.

Run the production image locally:

```bash
docker build -t news-analyser .
docker run -p 8000:8000 -e NEWS_PROVIDER=fake news-analyser   # http://localhost:8000
```

Production environment variables (set in Railway, never committed):

| Variable | Purpose |
|---|---|
| `NEWS_PROVIDER=gnews`, `GNEWS_API_KEY` | Live news |
| `APP_PASSWORD`, `SESSION_SECRET` | Puts the app behind a sign-in page (one shared password) so strangers can't spend the API quotas. `SESSION_SECRET` signs the session cookie. `/api/health` stays open for Railway's health check. |
| `DATABASE_URL` | Railway Postgres connection string (a reference variable). `postgresql://` URLs are converted to the psycopg driver automatically. |
| `NEWS_DAILY_REQUEST_LIMIT` | New searches allowed per UTC day (default 95; GNews free is 100) |
| `PORT` | Injected by Railway; defaults to 8000 |

## API

Interactive docs: `/docs` (OpenAPI). Main endpoints:

| Method & path | Purpose |
|---|---|
| `POST /api/searches` `{q, sort, period}` | Run a search. **201** = new; **200** = an identical search from the last 30 min was reused, so no news-API call was made. **429** once the daily quota is used. |
| `GET /api/searches?limit&offset` | Search history, newest first (with `total`). |
| `GET /api/searches/{id}` | A stored search with its articles. Never calls the news API. |
| `GET /api/quota` | News-API requests used and left today (resets 00:00 UTC). |
| `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/session` | Sign-in. |
| `GET /api/health` | App and database health. |

### Conventions

Every error response uses one shape:

```json
{ "error": { "code": "validation_error", "message": "Request validation failed", "details": [...] } }
```

## Decisions and tradeoffs

_To be written as features land._
