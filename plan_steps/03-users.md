# 03 — Users slice (users & members read views)

## Context & spec refs

Read-only projections over the `User` collection used to pick voting **managers** and voting
**recipients/members**. Endpoints #43 `GET /api/users`, #42 `GET /api/members`. Spec §4 (#42/#43),
§2 (User, Member); `CONVENTIONS.md` C9 (User ≠ Parliamentarian), C10 (bare arrays).

This slice reuses the `User` aggregate + `UserRepository` from doc 02 — it adds **query use cases +
API**, not a new table. Keep it thin (KISS): no new domain model.

## Application (`application/`)

- `ListUsersUseCase.execute() -> list[UserPublic]` — all users, **without `password`**.
- `ListMembersUseCase.execute() -> list[MemberDTO]` — projection `{ id, name, group }`.
- DTOs: reuse `UserPublic` (doc 02); `MemberDTO{ id, name, group }`.

## API (`api/router.py`) — routes under `/api`, both **Bearer** (C2 `current_user`)

### #43 `GET /api/users`
- 200 → **bare array** `[ <User> ]`. FE reads `id, name, role, group`. **Must not include
  `password`** (spec explicitly warns the mock leaked it). Include `club`/`group` fields.

### #42 `GET /api/members`
- 200 → **bare array** `[ { id, name, group } ]`.

## Cross-cutting conventions applied

C9 (these are `User`s, not parliamentarians — do not pull from the parliamentarian registry),
C10 (bare arrays), C2 (Bearer required).

## TDD checklist (red-first)

1. **`test_list_users_shape`** — authed GET → 200 list; each item has `id,name,role` and **no
   `password` key**.
2. **`test_list_users_requires_auth`** — no token → 401.
3. **`test_list_members_shape`** — authed GET → 200 list of `{id,name,group}` exactly.
4. **`test_members_source_is_user_collection`** — a seeded `User` appears in `/members`; a seeded
   `Parliamentarian` (different table) does **not** (guards C9).

## Definition of done

- #42/#43 return the correct bare-array shapes; no password leakage; auth enforced.
- No new persistence — verified to reuse doc 02's `UserRepository`.
