# 01 — Shared kernel (cross-cutting)

## Context & spec refs

The framework-agnostic base + cross-cutting infrastructure every slice reuses. No business
endpoints. Spec refs: §1.4 (auth header), §4.0 (public/optional auth), §8.1-2 (auth decisions),
§8.7 (permissions); `CONVENTIONS.md` C1–C3, C10, C11, C14.

Keep this lean (KISS/YAGNI): only what ≥2 slices actually need. Do not build a generic CQRS bus,
event sourcing, or a mediator — use cases are plain classes/functions called by routers.

## 1. `shared/domain/` — base building blocks

- `Entity` — dataclass base with `id: int | None`; equality by type+id.
- `AggregateRoot(Entity)` — marker for aggregate roots (Voting, Resolution, Session, Club,
  Parliamentarian, User).
- Value objects as frozen dataclasses per slice (defined in slices, not here) — but provide a
  couple of shared ones if reused: none required yet (YAGNI).
- `DomainError(Exception)` hierarchy with an HTTP mapping hint:
  - `NotFoundError(message)` → 404
  - `ConflictError(message)` → 400 (e.g. "already voted", "already signed")
  - `PermissionDeniedError(message)` → 403
  - `UnauthorizedError(message)` → 401
  - `ValidationError(message)` → 422/400
  Each carries a `.message` (Polish string from C11) and a `.status_code`.

## 2. `shared/application/` — use-case plumbing

- A thin `UseCase` protocol/base is optional; prefer plain classes with an async `execute(...)`.
- Repository **ports** are defined **in each slice's** `domain/` (dependency inversion), not here.
- Provide `UnitOfWork` only if needed; with `get_session` + repositories per request, an explicit
  UoW is usually unnecessary for v1 (YAGNI) — the request-scoped session *is* the UoW. Document
  that commits happen in `get_session` teardown.

## 3. `shared/api/` — HTTP glue

- **Exception handlers** registered in `main.py`: map each `DomainError` subtype to a JSON
  response `{ "message": err.message }` with `err.status_code`. Also a fallback handler for
  `RequestValidationError` returning `{ "message": ... }` shape when helpful (FE reads `message`).
- `envelopes.py` helpers: `wrapped(key, value)` etc. — but most wrapping is explicit per route
  (C10). Keep helpers minimal.
- No global pagination needed (spec returns full arrays); skip it (YAGNI) unless a slice asks.

## 4. `shared/auth/` — authentication & authorization

This is the most important shared piece. Files:

### `bearer.py` — tolerant Bearer extraction (C1)
`extract_jwt(authorization_header: str | None) -> str | None`:
- return `None` if header missing or not `Bearer `-prefixed.
- strip prefix; if the value starts with `{` → `json.loads` and return `.get("token")`.
- else return the value as-is. Wrap `json.loads` in try/except → `None` on failure.

### `jwt_service.py`
- `create_access_token(user_id: int, *, ttl_hours) -> str` (HS256, `sub=user_id`, `exp`).
- `decode_token(token: str) -> dict` (raises on invalid/expired). Wrap PyJWT.

### `deps.py` — FastAPI dependencies (C2)
- `optional_user(authorization: str = Header(None), session=Depends(get_session)) -> User | None`
  — extract → decode → load `User` by id; any failure returns `None` (never raises).
- `current_user(...)` — same but raises `UnauthorizedError("Wymagane uwierzytelnienie")` when the
  result is `None`.
- Both must load the **auth_identity** `User`. To avoid a hard import cycle, depend on a small
  `UserReader` port that the auth_identity slice provides/wires (or import its repository — a
  pragmatic direct import is acceptable for v1; document the choice).
- `identity_from_request(...)` helper implementing the priority chain in C2 (token → body
  `authorId`/`userId` → raise) for the token-optional-but-identity-needed endpoints.

### `rbac.py` — guards (C3)
- `is_admin(user) -> bool`.
- Dependency factories returning 403 `PermissionDeniedError("Brak uprawnień")` on denial:
  `require_manage_votings`, `require_admin_or_marshal`, `require_manage_parliamentarians`,
  `require_manage_resolutions`, `require_authenticated`.
- `can_manage_voting(user, voting) -> bool` (admin/MANAGE_VOTINGS or user in `voting.managers`).

## 5. `shared/storage/` — file storage (C14)

- `FileStorage` **port** (Protocol): `async save(subdir: str, filename: str, data: bytes) -> str`
  returning a public path (`/uploads/<subdir>/<filename>`); `path_for(subdir, filename) -> str`.
- `LocalDiskStorage` adapter writing under `settings.upload_dir`, ensuring subdirs exist,
  sanitizing filenames (avoid path traversal), de-duplicating names on collision.
- Used by resolutions (#19 docx) and votings (#15 attachments).

## Cross-cutting conventions applied

C1 (bearer), C2 (optional/required + identity chain), C3 (RBAC), C11 (error messages), C14
(storage), C10 (envelope helpers).

## TDD checklist (red-first)

1. **`test_extract_jwt_raw`** — `extract_jwt("Bearer abc.def.ghi") == "abc.def.ghi"`.
2. **`test_extract_jwt_json_wrapped`** — `extract_jwt('Bearer {"token":"abc","expiresAt":1}') ==
   "abc"`.
3. **`test_extract_jwt_missing_or_malformed`** — `None` for `None`, `"Basic x"`, `'Bearer {bad'`.
4. **`test_jwt_roundtrip`** — `decode_token(create_access_token(7))["sub"] == 7`; expired token
   raises.
5. **`test_optional_user_none_without_token`** — returns `None`, no raise.
6. **`test_current_user_401_without_token`** — raises `UnauthorizedError` with message
   `Wymagane uwierzytelnienie`.
7. **`test_rbac_denies_member`** — `require_manage_votings` raises 403 `Brak uprawnień` for a
   plain member; passes for admin and for `MANAGE_VOTINGS` holder.
8. **`test_can_manage_voting_via_managers`** — member listed in `voting.managers` → `True`.
9. **`test_local_disk_storage_saves_and_paths`** — save bytes → file exists, returned path is
   `/uploads/<subdir>/<name>`; traversal name is sanitized.
10. **`test_domain_error_to_http`** — each `DomainError` subtype maps to its status + `{message}`.

## Definition of done

- All 10 tests green.
- `optional_user`/`current_user`/RBAC guards importable and usable by slice routers.
- Bearer parser handles both FE shapes; storage adapter writes under `/uploads`.
