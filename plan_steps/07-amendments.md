# 07 — Amendments slice (poprawki)

## Context & spec refs

Amendments to resolutions: list/detail/create/withdraw + article `changes`. Endpoints #23, #23b,
#24, #25, #26, #27, #28. Spec §2 (Amendment), §4 (AMENDMENTS), §4.0; `CONVENTIONS.md` C2
(identity w/o token), C5 (slug-or-id parent), C10 (wrappers incl. `{data}`), C11, C13.

Depends on the resolutions slice (parent lookup). Coupling is by `resolutionId` + the shared
`resolve_resolution` helper (C5) — no hard module dependency beyond the repository port.

## Domain model (`slices/amendments/domain/`)

**`Amendment`** aggregate:
```
id: int
resolutionId: int
author: str
authorId: int
club: str | None
content: str                 # textual description
status: str                  # pending|accepted|rejected|withdrawn
createdAt: str               # "YYYY-MM-DD" (C13)
withdrawnReason: str | None
changes: list[Change]        # Change{ articleId, before, after, type? }
```
Value object `Change{ articleId: str|int, before: str, after: str, type?: "modify"|"add"|"delete" }`.
Conventions (spec §2): `before=null/""` → new article (`add`); `after="(usunięty)"`/`""` →
deletion (`delete`); `add` uses `articleId="new_<timestamp>"`.

Domain methods:
- `withdraw(actor, reason)` — only the author may withdraw (`authorId==actor.id`, else
  `PermissionDeniedError`); if already `withdrawn` → `ConflictError`; sets `status="withdrawn"`,
  `withdrawnReason=reason or "Brak podanego powodu"`.

Ports: `AmendmentRepository` (`get_by_id`, `list_by_resolution`, `list_all`, `add`, `update`).
Uses resolutions' `ResolutionRepository` + `resolve_resolution` (C5) to resolve the parent.

## Persistence (`infrastructure/`)

- `amendments` table; `changes` stored as JSON. `resolution_id` FK.
- Seed: 1–2 amendments on a seeded resolution (mix of `modify`/`add`/`delete`, one `pending`).

## Application (`application/`)

- `ListResolutionAmendmentsUseCase.execute(param) -> {resolution:{title,slug},
  session:{city,date}, amendments:[...]}` — `param` polymorphic (C5): `AmendmentsPage` passes
  slug, `FinalizeResolution` passes resolutionId.
- `CreateAmendmentUseCase.execute(param, body)` — resolve parent (C5/404), assign `id`,
  `createdAt`, `resolutionId`; identity from body `authorId` (C2). Return `{success:true, amendment}`.
- `GetAmendmentUnderResolutionUseCase` (#25) → `{resolution:{title,slug}, amendment, session:{city,date}}`.
- `ListAmendmentsUseCase` (#26) → **bare array**.
- `GetAmendmentUseCase` (#27) → `{ data: { ...amendment, resolution:{id,title,slug} } }` (wrapped
  in `data`).
- `WithdrawAmendmentUseCase.execute(id, actor, reason)` — identity via C2; author-only.
- DTOs mirror shapes.

## API (`api/router.py`) — under `/api`

### #23 / #23b `GET /api/resolutions/:slug/amendments` (public; slug **or** id — C5)
- 200 → `{ resolution:{title,slug}, session:{city,date}, amendments:[<Amendment>] }`.

### #24 `POST /api/resolutions/:slug/amendments` (public; identity from body)
- Body: `{ resolutionId, author, authorId, club, content, status:"pending", changes:[...],
  withdrawnReason:null }`. 201 → `{ success:true, amendment:<Amendment> }`. 404 if parent missing.

### #25 `GET /api/resolutions/:slug/amendments/:amendmentId` (public)
- 200 → `{ resolution:{title,slug}, amendment:<Amendment>, session:{city,date} }`. 404 →
  `{message:"Nie znaleziono poprawki"}`.

### #26 `GET /api/amendments` (Bearer)
- 200 → **bare array** `[<Amendment>]`.

### #27 `GET /api/amendments/:id` (Bearer)
- 200 → `{ "data": { ...Amendment, "resolution": {id,title,slug} } }`. 404 → `{message}`.

### #28 `POST /api/amendments/:id/withdraw` (public; identity from token/body, author-only)
- Body `{ reason }` (default "Brak podanego powodu"). 200 → `{ success:true, amendment:{...status:
  "withdrawn"} }`. 404 (missing), 400 (already withdrawn), 403 (not author).

## Cross-cutting conventions applied

C2 (create/withdraw identity), C5 (slug-or-id parent for #23/#23b/#24/#25), C10 (`{data}` wrapper
#27, bare array #26, composite wrappers), C11 (messages), C13 (`createdAt`).

## TDD checklist (red-first)

1. **`test_list_amendments_by_slug`** — GET by slug → `{resolution,session,amendments}`.
2. **`test_list_amendments_by_id_polymorphic`** — GET by numeric resolutionId → same shape (C5).
3. **`test_create_amendment`** — POST body → 201 `{success:true, amendment}`; server sets
   `id/createdAt/resolutionId`; `changes` preserved.
4. **`test_create_amendment_add_and_delete_conventions`** — `type:"add"` with `before=""` and
   `type:"delete"` with `after=""` round-trip intact.
5. **`test_create_404_missing_resolution`** — unknown parent → 404.
6. **`test_get_amendment_under_resolution`** — #25 shape; unknown amendment →
   `{message:"Nie znaleziono poprawki"}`.
7. **`test_list_amendments_bare_array`** — #26 authed → bare array.
8. **`test_get_amendment_wrapped_in_data`** — #27 → `{data:{...,resolution:{id,title,slug}}}`.
9. **`test_withdraw_by_author`** — author → 200 `{amendment.status=="withdrawn"}`, reason set.
10. **`test_withdraw_not_author_403`** — different user → 403.
11. **`test_withdraw_already_withdrawn_400`** — second withdraw → 400.
12. **`test_withdraw_default_reason`** — no reason → `withdrawnReason=="Brak podanego powodu"`.

## Definition of done

- All wrappers exact (esp. `{data}` for #27); slug-or-id parent resolution works; author-only
  withdraw enforced with correct 400/403/404; `changes` conventions preserved.
- Amendment status is flippable to accepted/rejected by votings #14 (expose repo update for
  `LinkedItemStatusUpdater`).
