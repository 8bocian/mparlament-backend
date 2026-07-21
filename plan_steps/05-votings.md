# 05 — Votings slice

## Context & spec refs

Largest slice: voting lifecycle + casting votes + computed live stats + attachments. Endpoints
#8–#16. Spec §2 (Voting, Vote), §4 (VOTING), §5 (realtime parity), §6.1.5-6, §8.4,8.7;
`CONVENTIONS.md` C3, C4 (abstain), C8 (recipients), C10, C13, C15 (status).

## Domain model (`slices/votings/domain/`)

**`Voting`** aggregate:
```
id: int
title: str
description: str | None
category: str            # resolution|amendment|law|budget|committee|other
startTime: str | None    # ISO 8601
endTime: str | None
status: str              # active|finished|upcoming|archived (C15)
recipientsType: str      # all|groups|members (map individual→members, C8)
selectedGroups: list[int]
selectedMembers: list[int]
linkedItemType: str      # none|resolution|amendment
linkedItemId: str | int | None
applicant: str | None    # marshal|presidium|group_15|individual | group id (string)
managers: list[int]      # user ids allowed to manage this voting
attachments: list[Attachment]
createdBy: str | None
# create-form options FE sends but does not read back (persist as-is / JSON):
quorumRequired, majorityType, allowAbstain, isAnonymous, requireComment,
canChangeVote, showResultsDuringVoting, notifyEmail, notifyPush
```
Value objects: `Attachment{ id, name, size, type, uploadDate }`.

**`Vote`** entity: `{ id, votingId, userId, value }` where `value ∈ {for, against, abstained}`
(normalized via C4 `normalize_vote`).

**Domain services / methods:**
- `normalize_vote(raw) -> "for"|"against"|"abstained"` (accept `abstain`/`abstained`).
- `cast_vote(user, raw)` — raise `ConflictError("Użytkownik już oddał głos")` if the user already
  voted (unless `canChangeVote` — v1: keep simple, reject double-vote per spec #12 error).
- `activate(startTime, endTime, duration, delay)` → `status="active"`, set times.
- `archive()` → `status="archived"`.
- `eligible_user_ids(users)` — resolve per `recipientsType` (C8).

**Computed (read-time) values** — NOT stored, derived by a query service from `Vote`s + eligible
users (spec §2 computed block):
```
votesFor, votesAgainst, abstained          # counts
votedCount, totalEligible
eligibleUsers, votedUsers, notVotedUsers    # each [{id,name,club}]
hasVoted, myVote                            # for the requesting user; myVote∈for|against|abstain|null
```
> Note: `myVote` returned to FE — spec shows `"for"|"against"|"abstain"|null`. Store `abstained`,
> but you may surface `myVote` as-is; keep it consistent — recommend returning stored value and
> letting FE treat `abstained`/`abstain` equivalently. Document the exact choice next to the code.

Ports: `VotingRepository` (get/list/add/update/delete), `VoteRepository`
(add/get_by_voting/get_user_vote/count_by_value), plus a `UserReader` (from users/auth) to expand
`{id,name,club}` and resolve eligibility.

## Persistence (`infrastructure/`)

- `votings` table: scalar columns + JSON columns for `selectedGroups`, `selectedMembers`,
  `managers`, `attachments`, and the option flags (or a single `options` JSON). `linkedItemId`
  stored as string (polymorphic).
- `votes` table: `{id, voting_id FK, user_id FK, value}` with a **unique (voting_id, user_id)**
  constraint (enforces single vote).
- Attachments: file bytes saved via `FileStorage` (doc 01); metadata in the voting's `attachments`
  JSON.
- Seed: 2–3 votings across statuses (active/upcoming/archived), one linked to a resolution.

## Application (`application/`)

Use cases:
- `ListVotingsUseCase.execute(requester, userId?, role?) -> list[VotingReadDTO]` (with computed).
- `GetVotingUseCase.execute(id, requester) -> VotingDetailDTO` (full computed incl. eligible/voted
  lists); raise `NotFoundError("Nie znaleziono głosowania")`.
- `CreateVotingUseCase` (RBAC MANAGE_VOTINGS) → returns created with `id`.
- `UpdateVotingUseCase` (RBAC).
- `CastVoteUseCase.execute(votingId, user, rawVote)` — normalize (C4), enforce single-vote, save;
  return `{ message?, vote }`.
- `ActivateVotingUseCase.execute(id, startTime, endTime, duration, delay)` (RBAC).
- `ArchiveVotingUseCase.execute(id)` — set archived **and** update linked item status
  (`votesFor>votesAgainst ? accepted : rejected`) via a `LinkedItemStatusUpdater` port
  (implemented against resolutions/amendments repos — loose coupling by id).
- `AddAttachmentsUseCase.execute(id, files)` (RBAC) — fire-and-forget; store + append metadata.
- `DeleteVotingUseCase` (#16, handler-only).
- DTOs: `VotingReadDTO`, `VotingDetailDTO`, `CreateVotingRequest`, `VoteRequest{vote}`,
  `ActivateRequest{startTime,endTime,duration,delay}`.

## API (`api/router.py`) — under `/api`, all **Bearer**

### #8 `GET /api/votings` (Bearer, `?userId=&role=` optional)
- 200 → **bare array** of votings **with computed fields** (`votesFor/Against/abstained`,
  `hasVoted`, `myVote`, `votedCount`, ...). FE does `data.forEach/.map` — must be an array.

### #9 `GET /api/votings/:id` (Bearer)
- 200 → full voting + computed incl. `eligibleUsers, votedUsers, notVotedUsers, totalEligible,
  votedCount, hasVoted, myVote`. 404 → `{message:"Nie znaleziono głosowania"}`.

### #10 `POST /api/votings` (Bearer, MANAGE_VOTINGS/admin)
- Body = full Voting. 201 → created object with `id` (FE reads `data.id`, then maybe #15).

### #11 `PUT /api/votings/:id` (Bearer, MANAGE_VOTINGS or manager)
- Body like #10 (EditVoting omits `managers`). 200 → updated object (FE only checks `response.ok`
  + maybe `data.message`). Returning `{success, message, voting}` OR the bare object both work —
  pick the bare object for consistency and include `message`.

### #12 `POST /api/votings/:id/vote` (Bearer)
- Body `{ vote: "for"|"against"|"abstain" }`. 200 → `{ message?, vote }` (FE sets `myVote=data.vote`).
- 400 `{message:"Użytkownik już oddał głos"}`; 404 `{message:"Nie znaleziono głosowania"}`.
- Normalize `abstain→abstained` (C4).

### #13 `POST /api/votings/:id/activate` (Bearer, RBAC)
- Body `{ startTime, endTime, duration, delay }`. → `status=active`. 200 → `{success, message, voting}`.

### #14 `POST /api/votings/:id/archive` (Bearer, RBAC, no body)
- → `status=archived` + update linked item status by result. 200 → `{ success: true, voting }`.

### #15 `POST /api/votings/:id/attachments` (Bearer, multipart)
- Fields `attachment_0, attachment_1, ...`. FE ignores response (fire-and-forget). 200 → `{success:true}`.
- Validate size (FE caps ~10MB — enforce server-side too).

### #16 `DELETE /api/votings/:id` (handler-only)
- 200 → `{ success: true }`.

## Cross-cutting conventions applied

C3 (MANAGE_VOTINGS + manager rights), C4 (abstain normalize), C8 (recipients incl. individual→
members), C10 (bare array #8, computed shapes), C13 (ISO/datetime-local parsing), C15 (persist
status; authoritative archived/active), linked-item update (C via resolutions/amendments).

## TDD checklist (red-first)

1. **`test_normalize_vote`** — `abstain`→`abstained`; `abstained`→`abstained`; `for/against`
   unchanged; invalid → ValidationError.
2. **`test_eligibility_all`** — `recipientsType=all` → every user eligible.
3. **`test_eligibility_members_and_individual`** — `members` and `individual` both resolve via
   `selectedMembers` (C8).
4. **`test_eligibility_groups`** — only users in `selectedGroups`.
5. **`test_list_votings_is_array_with_computed`** — 200 array; each has `votesFor,votesAgainst,
   abstained,votedCount,hasVoted,myVote`.
6. **`test_get_voting_detail_lists`** — `eligibleUsers/votedUsers/notVotedUsers` present as
   `{id,name,club}`; `totalEligible == len(eligibleUsers)`.
7. **`test_get_voting_404`** — unknown id → 404 `Nie znaleziono głosowania`.
8. **`test_cast_vote_sets_myvote`** — POST vote → 200 `{vote}`; subsequent GET has `hasVoted=true`,
   correct `myVote`, and the count incremented.
9. **`test_cast_vote_twice_conflict`** — second vote → 400 `Użytkownik już oddał głos`.
10. **`test_cast_abstain_counts_as_abstained`** — POST `{vote:"abstain"}` increments `abstained`.
11. **`test_create_requires_manage_votings`** — member → 403; admin/MANAGE_VOTINGS → 201 with `id`.
12. **`test_manager_can_edit`** — user in `managers` can PUT even without MANAGE_VOTINGS.
13. **`test_activate_sets_active`** — status→active, times set; RBAC enforced.
14. **`test_archive_sets_archived_and_updates_linked_resolution`** — with a linked resolution and
    votesFor>votesAgainst → resolution status `accepted`; reverse → `rejected`.
15. **`test_attachments_multipart_stored`** — POST `attachment_0` file → 200 `{success:true}`; file
    saved; metadata appears in voting `attachments`.
16. **`test_delete_voting`** — DELETE → `{success:true}`; gone from list.

## Definition of done

- All computed fields correct against seeded votes; #8 returns an array.
- Single-vote enforced (unique constraint + 400); abstain normalized; archive cascades to linked
  item status.
- RBAC (MANAGE_VOTINGS + managers) enforced on writes; attachments stored via `FileStorage`.
- Live-parity note: `GET /api/votings/:id` returns the same fields the realtime `voteUpdate` event
  would (spec §5) so the FE 3s polling fallback works — verified by test 8.
