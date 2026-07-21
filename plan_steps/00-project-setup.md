# 00 — Project setup & skeleton

## Context & spec refs

Foundation for every slice. Establishes tooling, config, async DB, migrations, the ASGI app
factory, static file serving, and the pytest harness. Spec refs: §7 (dev-setup), §1.4 (auth),
`CONVENTIONS.md` C14. No business endpoints here.

## 1. Dependencies (Poetry, Python 3.12)

Update `pyproject.toml`: set `requires-python = ">=3.12"`. Add (via `poetry add`):

Runtime:
- `fastapi`, `uvicorn[standard]`
- `sqlalchemy[asyncio]>=2.0`, `aiosqlite`
- `alembic`
- `pydantic>=2`, `pydantic-settings`
- `python-multipart` (multipart uploads)
- `pyjwt` (JWT; simpler than python-jose), `passlib[bcrypt]` (password hashing)
- `python-slugify` optional — or hand-roll per C12 (prefer hand-roll to control Polish chars).

Dev (`poetry add --group dev`):
- `pytest`, `pytest-asyncio`, `httpx`, `anyio`
- `ruff` (lint+format), `mypy` (optional but encouraged)

Keep dependencies minimal (YAGNI): do **not** add `python-socketio` yet (deferred, doc 10).

## 2. Directory skeleton

Create exactly the tree from the plan's architecture section:

```
src/mparlament/
  __init__.py
  main.py
  shared/{__init__.py, config.py, db.py,
          domain/, application/, api/, auth/, storage/}
  slices/{__init__.py,
          auth_identity/, users/, sessions/, votings/, resolutions/,
          amendments/, parliamentarians_clubs/, groups_members/}
    <each slice>/{__init__.py, domain/, application/, infrastructure/, api/, tests/}
  migrations/
tests/
```

Configure Poetry packages: `packages = [{ include = "mparlament", from = "src" }]`.

## 3. `shared/config.py` — settings

`Settings(BaseSettings)` via `pydantic-settings`, env-prefixed (`MPARLAMENT_`), `.env` support:
- `database_url: str = "sqlite+aiosqlite:///./mparlament.db"`
- `jwt_secret: str`, `jwt_algorithm: str = "HS256"`, `jwt_ttl_hours: int = 10` (spec TTL 10h)
- `upload_dir: Path = Path("uploads")`
- `cors_origins: list[str] = ["http://localhost:5173"]`
- `host: str = "0.0.0.0"`, `port: int = 4000`

Expose a cached `get_settings()`.

## 4. `shared/db.py` — async SQLAlchemy

- `create_async_engine(settings.database_url)`.
- `async_sessionmaker(engine, expire_on_commit=False)`.
- `class Base(DeclarativeBase): ...`.
- `async def get_session() -> AsyncIterator[AsyncSession]` FastAPI dependency (yields, commits on
  success / rolls back on exception, closes).
- Enable SQLite FK enforcement: on `connect`, `PRAGMA foreign_keys=ON` (async event listener).

## 5. Alembic (async)

- `alembic init migrations`, then convert `env.py` to async (`run_async_migrations` using the
  async engine; import `Base.metadata` as `target_metadata`; pull URL from `Settings`).
- All slice ORM models must be imported in a central place (e.g. `shared/db.py` re-exports or a
  `models_registry`) so Alembic autogenerate sees them.
- First migration is authored per-slice; for local/dev convenience also support
  `Base.metadata.create_all` in tests (see §8).

## 6. `main.py` — app factory

`create_app() -> FastAPI`:
1. `app = FastAPI(title="mparlament-backend")`.
2. Add `CORSMiddleware` (origins from settings; allow `Authorization`, `Content-Type`; allow
   credentials; all methods; preflight).
3. Register exception handlers from `shared/api` (DomainError → JSON `{message}`; see doc 01).
4. Include each slice's `router` under prefix `/api` (each slice router already carries its
   sub-path). Realtime not mounted in v1.
5. Mount static files: `app.mount("/uploads", StaticFiles(directory=settings.upload_dir))` so
   `/uploads/resolutions/<fileName>` resolves (C14).
6. Optional startup: ensure `upload_dir/resolutions` exists.

`uvicorn` entrypoint runs `create_app()` on `settings.port` (4000).

## 7. Seed data (from MSW fixtures)

Provide `scripts/seed.py` (or a `seed` module) that inserts the sample data the FE's MSW used, so
the running backend has a login that works and demo votings/resolutions. Mirror the shapes in
spec §2. At minimum: one admin user (`TEST123`), a couple members with clubs/groups, one current
session, 2–3 votings, 1–2 resolutions with chapters, a club or two, parliamentarians. Seed is
idempotent. (Downstream: transcribe actual values from the frontend's `src/mocks/data/*` if
available; otherwise synthesize consistent demo data.)

## 8. pytest harness (TDD backbone)

`tests/conftest.py` provides:
- `event_loop`/anyio backend config for async tests.
- A **per-test SQLite** database (in-memory `sqlite+aiosqlite:///:memory:` with a shared
  connection, or a temp file per test) created via `Base.metadata.create_all` in a fixture, then
  dropped. This keeps unit/integration tests fast and isolated (no Alembic needed in tests).
- `async_session` fixture yielding an `AsyncSession` bound to the test DB.
- `client` fixture: `httpx.AsyncClient(transport=ASGITransport(app=create_app()))` with
  `get_session` dependency overridden to the test session; base_url `http://test`.
- `auth_headers(user)` helper that mints a valid JWT and returns
  `{"Authorization": f"Bearer {jwt}"}`, plus a variant returning the **JSON-wrapped** bearer to
  test the tolerant parser (C1).

## Cross-cutting conventions applied

C14 (port 4000, `/uploads`, CORS, multipart), C1 (test both bearer shapes).

## TDD checklist (red-first)

1. **`test_app_boots`** — `create_app()` returns a FastAPI instance; `GET /api/health` (add a
   trivial health route) → 200 `{ "status": "ok" }`.
2. **`test_cors_preflight`** — `OPTIONS /api/health` with `Origin: http://localhost:5173` →
   `access-control-allow-origin` present.
3. **`test_static_uploads_mounted`** — write a file under `upload_dir/resolutions/x.txt`, GET
   `/uploads/resolutions/x.txt` → 200.
4. **`test_db_session_fixture`** — a trivial insert/select round-trips on the test session.
5. **`test_settings_defaults`** — `get_settings().port == 4000`,
   `database_url.startswith("sqlite+aiosqlite")`.

## Definition of done

- `poetry install` succeeds on 3.12; `pytest` runs (the 5 tests above green).
- `uvicorn` boots the app on `:4000`; `GET /api/health` works; `/uploads/...` serves files.
- `alembic revision --autogenerate` produces a migration once models exist.
- Skeleton dirs + `__init__.py` present for all slices.
