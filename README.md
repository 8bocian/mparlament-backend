# mparlament-backend

Python backend (FastAPI + SQLAlchemy async + Alembic + Pydantic v2) for **Parlament Młodych RP**,
replacing the frontend's MSW mock. `BACKEND_SPEC.md` is the source of truth (the contract the React
frontend expects). Architecture: Domain-Driven Design + vertical slices + TDD.

## Requirements

- Python 3.12
- [Poetry](https://python-poetry.org/) 2.x

## Setup

```bash
poetry install
```

## Run

```bash
poetry run uvicorn mparlament.main:app --host 0.0.0.0 --port 4000 --reload
```

The API is served under `/api` (e.g. `GET /api/health` → `{"status": "ok"}`); uploaded files are
served from `/uploads/...`. Configure via `MPARLAMENT_`-prefixed env vars or a `.env` file
(see `src/mparlament/shared/config.py`).

## Test

```bash
poetry run pytest
```

Async tests use the anyio pytest plugin; each test runs against an isolated in-memory SQLite DB.

## Database migrations

```bash
poetry run alembic revision --autogenerate -m "message"
poetry run alembic upgrade head
```

## Seed dev data

```bash
poetry run python scripts/seed.py
```

## Layout

```
src/mparlament/
  main.py                 # ASGI app factory (create_app)
  shared/                 # shared kernel: config, db, auth, storage, base classes
  slices/<slice>/         # vertical slices: domain / application / infrastructure / api / tests
migrations/               # Alembic (async env.py)
scripts/seed.py           # idempotent dev seed
tests/                    # cross-cutting test harness (conftest.py)
plan_steps/               # per-feature implementation briefs
```
