# 09 — Groups (& members recap) slice

## Context & spec refs

Supplies the **groups** list used when choosing voting recipients. Endpoint #41 `GET /api/groups`.
(`GET /api/members` #42 is implemented in doc 03 — recapped here for the recipient use case.)
Spec §2 (Group, Member), §4 (#41/#42); `CONVENTIONS.md` C8 (recipients), C10 (bare arrays).

Thin slice — keep it minimal (YAGNI). Groups may be a small standalone table, or derived from the
distinct `User.group` values. Recommended: a real `groups` table so `selectedGroups: int[]` on
votings references stable ids.

## Domain model (`slices/groups_members/domain/`)

**`Group`** entity: `{ id, name, memberCount? }` (`memberCount` optional — FE shows
`group.memberCount || 0`). Port `GroupRepository` (`list_all`). `memberCount` computed as the
number of `User`s whose `group` maps to this group (via a `UserReader`).

No new model for members — reuse doc 03's `MemberDTO{ id, name, group }`.

## Persistence (`infrastructure/`)

- `groups` table `{id, name}`. Seed a couple of groups consistent with seeded users' `group`
  field and any `selectedGroups` used in seeded votings.

## Application (`application/`)

- `ListGroupsUseCase.execute() -> list[GroupDTO]` — id, name, optional memberCount.

## API (`api/router.py`) — under `/api`, **Bearer**

### #41 `GET /api/groups` (Bearer)
- 200 → **bare array** `[{ id, name }]` (optionally `memberCount`).

## Cross-cutting conventions applied

C8 (groups are what `selectedGroups`/`recipientsType=groups` resolve against — keep group ids
stable and consistent with users' `group`), C10 (bare array).

## TDD checklist (red-first)

1. **`test_groups_bare_array`** — authed GET → bare array `[{id,name}]`.
2. **`test_groups_membercount_optional`** — when included, `memberCount` equals the number of
   users in that group.
3. **`test_groups_ids_align_with_voting_selectedGroups`** — a seeded voting's `selectedGroups`
   ids exist in `/api/groups` (keeps eligibility resolvable — C8).
4. **`test_groups_requires_auth`** — no token → 401.

## Definition of done

- `/api/groups` returns the correct shape; group ids are consistent with `User.group` and voting
  `selectedGroups` so votings-eligibility (doc 05, C8) resolves correctly.
