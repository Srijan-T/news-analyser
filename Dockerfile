# syntax=docker/dockerfile:1
# One image for the whole app: FastAPI serves the API and the built React frontend.

# ---- Stage 1: build the frontend --------------------------------------------------------
FROM node:24-slim AS frontend
WORKDIR /frontend
# Copy manifests first so `npm ci` stays cached until dependencies change.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: Python runtime -----------------------------------------------------------
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.17 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first (cached layer), then the app code, which changes more often.
# Plain COPY rather than RUN --mount: Railway's builder rejects bind mounts, and cache mounts
# without a Railway-specific id, so this Dockerfile uses no --mount flags at all.
ENV UV_NO_CACHE=1
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY backend/ ./
RUN uv sync --locked --no-dev

COPY --from=frontend /frontend/dist ./static

ENV PATH="/app/.venv/bin:$PATH" \
    STATIC_DIR=/app/static \
    APP_ENV=production

# Don't run as root.
RUN useradd --system --no-create-home app
USER app

EXPOSE 8000
# Railway sets PORT; default to 8000 elsewhere. --proxy-headers trusts Railway's proxy for
# the client's scheme and IP.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
