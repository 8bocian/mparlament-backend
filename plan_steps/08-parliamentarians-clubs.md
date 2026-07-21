# 08 — Parliamentarians & Clubs slice

## Context & spec refs

Chamber registry: parliamentarians and their clubs (separate from `User` — C9). Endpoints #29–#38.
Spec §2 (Parliamentarian, Club), §4 (PARLIAMENTARIANS, CLUBS), §6.1.7, §8.5; `CONVENTIONS.md` C3
(MANAGE_PARLIAMENTARIANS), C7 (POST upsert + PUT), C9 (distinct from users), C10 (wrappers).

## Domain model (`slices/parliamentarians_clubs/domain/`)

**`Parliamentarian`** aggregate:
```
id: int
firstName: str
lastName: str
clubId: int | None          # null ⇒ unaffiliated
clubName: str | None        # expanded from club (null when unaffiliated)
clubColor: str | None       # expanded from club
functions: list[str]
commissions: list[str]
```
**`Club`** aggregate:
```
id: int
name: str
type: str                   # "klub"|"koło"|"komitet"
color: str
members: list[ClubMember]   # ClubMember{ id, firstName, lastName, functions, commissions }
```
Invariants: `type` from the allowed set; deleting a club unlinks its parliamentarians
(`clubId→null`); deleting a parliamentarian removes it from its club's membership. `clubName`/
`clubColor` are always derived from the referenced club at read time (not stored redundantly, or
kept in sync).

Ports: `ParliamentarianRepository` (get/list/add/update/delete/upsert),
`ClubRepository` (get/list/add/update/delete). A domain service expands `clubName/clubColor` and
partitions into affiliated/unaffiliated.

## Persistence (`infrastructure/`)

- `clubs` table `{id, name, type, color}`. (Members are derived from parliamentarians, not stored
  on the club — spec §6.1.7 notes club data has no `members`; return `members:[]` or expanded.)
- `parliamentarians` table `{id, firstName, lastName, club_id FK nullable, functions JSON,
  commissions JSON}`.
- Seed: 2 clubs (different types/colors) + several parliamentarians (some unaffiliated).

## Application (`application/`)

- `ListParliamentariansUseCase` → `{ parliamentarians:[clubId!=null...], unaffiliated:[clubId==null...] }`
  with `clubName/clubColor` expanded (C10).
- `UpsertParliamentarianUseCase.execute(body)` (#30) — if `body.id` matches existing → update,
  else create (C7). Expand `clubName/clubColor` from `clubId` in response.
- `UpdateParliamentarianUseCase` (#31 PUT).
- `DeleteParliamentarianUseCase` (#32) — unlink from club.
- `ListClubsUseCase` (#33) → **bare array**; `members:[]` (FE computes counts from parliamentarian
  list, not from `members`).
- `CreateClubUseCase` (#34) / `UpdateClubUseCase` (#35) / `DeleteClubUseCase` (#36, unlink members).
- (#37/#38 club-member add/remove — handler-only; optional. Return `{club, parliamentarians,
  unaffiliated}`.)
- DTOs mirror shapes.

## API (`api/router.py`) — under `/api`, **Bearer + MANAGE_PARLIAMENTARIANS/admin** on writes

### #29 `GET /api/parliamentarians` (Bearer)
- 200 → `{ parliamentarians:[<P clubId!=null>], unaffiliated:[<P clubId=null>] }`.

### #30 `POST /api/parliamentarians` (Bearer, RBAC) — **upsert (C7)**
- Body `{ firstName, lastName, clubId(int|null), functions[], commissions[], id? }`. 200/201 →
  created/updated `<Parliamentarian>` with expanded `clubName/clubColor`.

### #31 `PUT /api/parliamentarians/:id` (Bearer, RBAC)
- Body like #30. 200 → updated object.

### #32 `DELETE /api/parliamentarians/:id` (Bearer, RBAC)
- 200 → `{ success:true }`; unlinked from club.

### #33 `GET /api/clubs` (Bearer)
- 200 → **bare array** `[<Club>]` (FE reads `id,name,type,color`; `members:[]` acceptable).

### #34 `POST /api/clubs` (Bearer, RBAC)
- Body `{ name, type, color }`. 201 → `<Club>` with `id` and `members:[]`.

### #35 `PUT /api/clubs/:id` (Bearer, RBAC)
- Body like #34. 200 → updated `<Club>`.

### #36 `DELETE /api/clubs/:id` (Bearer, RBAC)
- 200 → `{ success:true }`; members' `clubId→null`.

### #37 / #38 `POST/DELETE /api/clubs/:id/members[/:memberId]` (optional, handler-only)
- 200 → `{ club, parliamentarians, unaffiliated }`.

## Cross-cutting conventions applied

C3 (MANAGE_PARLIAMENTARIANS/admin on writes), C7 (POST upsert + PUT both work), C9 (registry is
separate from `User`), C10 (`{parliamentarians,unaffiliated}`, bare clubs array).

## TDD checklist (red-first)

1. **`test_list_partitions_affiliated_unaffiliated`** — response splits by `clubId`;
   `clubName/clubColor` expanded for affiliated, null for unaffiliated.
2. **`test_post_creates_new`** — POST without `id` → new parliamentarian with expanded club fields.
3. **`test_post_upserts_existing`** — POST with existing `id` → updates in place (no duplicate) — C7.
4. **`test_put_updates`** — #31 updates; RBAC enforced.
5. **`test_delete_unlinks`** — delete parliamentarian → removed; club membership no longer lists it.
6. **`test_clubs_bare_array`** — #33 → bare array with `id,name,type,color`.
7. **`test_create_club`** — #34 → 201 `<Club>` with `id`, `members:[]`.
8. **`test_delete_club_unlinks_members`** — after club delete, its parliamentarians have
   `clubId==null` and appear in `unaffiliated`.
9. **`test_writes_require_manage_parliamentarians`** — member → 403; admin/MANAGE_* → ok.

## Definition of done

- Partitioned list shape + expanded club fields correct; POST-as-upsert prevents the FE's
  duplicate-on-edit bug (C7); club delete cascades to `clubId=null`; RBAC enforced; registry kept
  separate from the `User` collection (C9).
