# syntax=docker/dockerfile:1

# Single-image deployment: the built React SPA and the API are served from one origin, so the
# frontend's relative fetch("/api/...") calls and its same-origin Socket.IO connection work
# unchanged in production. See DEPLOYMENT.md.

# The frontend lives in its own repository, so it is fetched by ref at build time.
# Pin FRONTEND_REF to a commit SHA for reproducible builds; a branch name also works, but a
# cached layer may then hold a stale clone (on Render: "Clear build cache & deploy").
ARG FRONTEND_SLUG=Macions/mparlament
ARG FRONTEND_REF=main


# --- Stage 1: build the SPA --------------------------------------------------------------
# Debian (glibc), not Alpine: Vite 8 pulls in native rolldown binaries, and npm picks the
# right one from the `libc` fields in package-lock.json. A musl base makes that selection
# fragile, and this stage is thrown away anyway -- only dist/ is copied into the runtime.
FROM node:22-bookworm-slim AS frontend

ARG FRONTEND_SLUG
ARG FRONTEND_REF

RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# `git fetch <ref>` (unlike `clone --branch`) accepts a branch, tag or commit SHA.
RUN git init -q . \
 && git remote add origin "https://github.com/${FRONTEND_SLUG}.git" \
 && git fetch --depth 1 origin "${FRONTEND_REF}" \
 && git checkout -q FETCH_HEAD

RUN npm ci

# --base=/ overrides the repo's gh-pages base (/mparlament/): here the app is served from the
# domain root.
RUN npm run build -- --base=/


# --- Stage 2: runtime --------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src \
    MPARLAMENT_STATIC_DIR=/app/static \
    MPARLAMENT_UPLOAD_DIR=/app/uploads \
    MPARLAMENT_DATABASE_URL=sqlite+aiosqlite:////app/data/mparlament.db

WORKDIR /app

RUN pip install --no-cache-dir "poetry==2.1.1"

# Dependencies first: this layer is cached until pyproject.toml / poetry.lock change.
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.create false \
 && poetry install --only main --no-root

COPY alembic.ini ./
COPY migrations ./migrations
COPY scripts ./scripts
COPY src ./src
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY --from=frontend /build/dist ./static

# /app/data (SQLite) and /app/uploads are the only writable paths — mount a volume on them to
# survive restarts; on an ephemeral filesystem they are recreated by the entrypoint's seed.
RUN chmod +x /usr/local/bin/entrypoint.sh \
 && mkdir -p /app/data /app/uploads/resolutions \
 && useradd --create-home --uid 10001 app \
 && chown -R app:app /app
USER app

EXPOSE 4000
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
