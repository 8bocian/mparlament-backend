# 02 — Auth & Identity slice

## Context & spec refs

Login + "who am I". Everything authed depends on this. Endpoints #1, #2, #2b, #3.
Spec §1.4, §4 (AUTH), §4.0; `CONVENTIONS.md` C1, C2, C6, C11. Owns the `User` aggregate (also
consumed by the `users` slice, doc 03, and as voter identity across the app — C9).

## Domain model (`slices/auth_identity/domain/`)

`User` aggregate (dataclass):
```
id: int
username: str          # login, e.g. "TEST123"
password_hash: str     # never serialized
name: str              # "Jan Kowalski"
club: str | None       # club name as text (FE uses as party/club)
role: Role             # "admin" | "marshal" | "member"
permissions: list[str] # subset of MANAGE_VOTINGS/MANAGE_RESOLUTIONS/MANAGE_PARLIAMENTARIANS
group: str | None      # used by voting recipients (GET /users reads group)
```
- `Role` value object / `StrEnum`.
- Invariant: `permissions` only from the allowed set; `role` from the enum.
- Domain method `is_admin()` mirroring C3 (or keep in rbac helper — pick one home, reference it).
- Port `UserRepository`: `get_by_id`, `get_by_username`, `list_all`.
- Domain service `verify_password(raw, hash)` / `hash_password(raw)` wrap `passlib` (in infra, port
  in domain if you prefer inversion; simplest: a `PasswordHasher` port).

## Persistence (`infrastructure/`)

`users` table (SQLAlchemy model): columns mirror the entity; `permissions` stored as JSON/text
(SQLite: `JSON` type or comma-separated → prefer SQLAlchemy `JSON`). `password_hash` column.
Mapper `to_domain`/`to_orm`. Repository adapter implements the port. Unique index on `username`.

Seed: at least one admin (`username="TEST123"`) with a bcrypt hash of a known dev password, plus a
couple of members with `club`/`group` set.

## Application (`application/`)

Use cases + DTOs (Pydantic):
- `LoginUseCase.execute(username, password) -> LoginResult` → verify hash; on failure raise
  `UnauthorizedError("Nieprawidłowy login lub hasło")`; on success issue JWT (C1 jwt_service).
- `GetMeUseCase.execute(user) -> UserDTO`.
- DTOs: `LoginRequest{username,password}`, `LoginResponse{token, user: UserPublic}`,
  `UserPublic{id, username, name, role, club, permissions}` (**no password**).

## API (`api/router.py`) — routes under `/api`

### #1 `POST /api/auth/login` (public)
- Body `LoginRequest`. 200 → `{ "token": <jwt>, "user": { id, username, name, role, permissions } }`
  (spec §4.1; `club` may be included too — FE gets it from `/me`). 401 →
  `{ "message": "Nieprawidłowy login lub hasło" }`.

### #2 / #2b `GET /api/auth/me` (optional auth — C2)
- Uses `optional_user`. If identity known → 200 bare user
  `{ id, username, name, role, club, permissions }`. If not → 401 `{ "message": ... }`.
- Both the Bearer and no-Bearer callers hit the same route; tolerant parser (C1) handles the
  malformed header.

### #3 `GET /api/current-user` (public/optional)
- Same identity resolution; 200 → **wrapped**: `{ "user": <User> }` (C6). 401 → `{ "message": ... }`.

## Cross-cutting conventions applied

C1 (tolerant bearer on `/me`), C2 (optional_user), C6 (bare vs `{user}` wrapper), C11 (login
error), never return `password` (C10 / spec §2 User).

## TDD checklist (red-first)

1. **`test_login_success`** — seeded creds → 200; body has `token` (non-empty) and
   `user.id/name/role/permissions`; **no `password` field anywhere**.
2. **`test_login_bad_credentials`** — wrong password → 401 `{message:"Nieprawidłowy login lub hasło"}`.
3. **`test_login_unknown_user`** — 401 same message (don't leak which field was wrong).
4. **`test_me_with_bearer`** — token from login in `Authorization` → 200 bare user incl. `club`.
5. **`test_me_with_json_wrapped_bearer`** — send `Bearer {"token":"<jwt>","expiresAt":...}` →
   still 200 (C1).
6. **`test_me_without_token`** — 401 `{message}`.
7. **`test_current_user_wrapped`** — `GET /api/current-user` → 200 `{ "user": {...} }` (wrapped);
   401 when anonymous.
8. **`test_jwt_encodes_user`** — issued token decodes to the right user id.
9. **`test_password_hash_verified`** — `verify_password` true for correct, false for wrong.

## Definition of done

- #1/#2/#2b/#3 pass integration tests with exact shapes and Polish error messages.
- Tolerant bearer verified end-to-end (test 5).
- `password` never appears in any response; JWT TTL honors settings (10h).
- `UserRepository` + issued JWT are consumable by `shared/auth` deps (doc 01) for all other slices.
