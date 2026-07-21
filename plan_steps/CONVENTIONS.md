# CONVENTIONS.md — cross-slice decisions (read before every feature)

This resolves every open/ambiguous item in `../BACKEND_SPEC.md` §6 and §8 with a **concrete,
enforceable rule**. Feature docs link here instead of re-explaining. When a feature doc and this
file disagree, this file wins; when this file and the spec disagree, the spec's *frontend
behaviour* wins (we exist to make that FE work unchanged).

---

## C1. Auth header parsing (spec §1.4, §8.1) — tolerant, zero FE changes

The FE sends `Authorization: Bearer <X>` where `<X>` is **either** a raw JWT **or** the JSON
string `{"token":"<jwt>","expiresAt":<ms>}` (it stores the whole localStorage `token` blob).

**Rule:** the Bearer parser (`shared/auth/bearer.py`) must:
1. Strip the `Bearer ` prefix.
2. If the remainder `startswith("{")` → `json.loads` it and take `["token"]`.
3. Otherwise treat the remainder as the JWT directly.
4. Verify/decode the resulting JWT normally.

Any failure → treat as **no identity** (not a hard 401 at the parser level; see C2).

## C2. Optional auth vs required auth (spec §4.0, §6.1.8, §8.2)

Some endpoints are called sometimes with a token, sometimes without, and some token-less
endpoints still need to know "who am I" (sign, withdraw, `/me` variants).

Two FastAPI dependencies in `shared/auth/deps.py`:
- `current_user` → **requires** a valid identity; raises 401 `{ "message": <msg> }` if absent.
- `optional_user` → returns `User | None`; never raises. Used by reads that personalize when a
  token is present and serve public data otherwise.

**Identity-needed-but-token-optional endpoints** (#21 sign, #22 unsign, #28 withdraw, #2b/#3 me):
resolve identity in this priority order and use the first that yields a user:
1. `optional_user` (token if the FE happened to send one),
2. explicit `authorId`/`userId` in the request body when the FE provides it (#24 create-amendment
   carries `authorId`; withdraw checks author),
3. otherwise → 401 `{ "message": "Wymagane uwierzytelnienie" }`.

Document per-endpoint which apply; never invent a session cookie for v1 (YAGNI).

## C3. Permission model (spec §8.7) — enforced server-side

`User.role ∈ {admin, marshal, member}`, `User.permissions ⊆ {MANAGE_VOTINGS,
MANAGE_RESOLUTIONS, MANAGE_PARLIAMENTARIANS}`. Helper `is_admin(user) = role=="admin" or any
MANAGE_* in permissions` mirrors the FE.

| Capability | Allowed when |
|---|---|
| Create/edit/activate/archive voting; view live eligible/voted lists | `admin` OR `MANAGE_VOTINGS` OR user ∈ that voting's `managers[]` |
| Manage session (`PUT /session/current`), add speakers, finalize resolutions | `admin` OR `marshal` (finalize also `MANAGE_RESOLUTIONS`) |
| CRUD parliamentarians & clubs | `admin` OR `MANAGE_PARLIAMENTARIANS` |
| Vote; sign/unsign own signature; add amendment; withdraw **own** amendment | `member` (any authenticated user) |

Guards live in `shared/auth/rbac.py` as FastAPI dependencies (e.g. `require_manage_votings`,
`require_admin_or_marshal`). On denial → 403 `{ "message": "Brak uprawnień" }`.

## C4. Abstain enum (spec §2 Vote, §6.1.5, §8.4)

Canonical stored value = **`"abstained"`**. The vote endpoint (#12) accepts `"for"`, `"against"`,
`"abstain"`, **and** `"abstained"` on input and normalizes `"abstain" → "abstained"`. The stat
field returned to the FE is `abstained` (a count). Normalization helper:
`normalize_vote(value)` in the votings domain.

## C5. Polymorphic path params (spec §6.1.2-3, §8.3)

For `GET /api/resolutions/:slug` (#18/#18b) and `GET /api/resolutions/:x/amendments` (#23/#23b):
if the path segment matches `^\d+$` → look up by **integer id**; otherwise by **slug**. Provide a
shared helper `resolve_resolution(param, repo)` used by both resolutions and amendments slices.

## C6. Path aliases + superset payloads (spec §6.1.1, §6.1.4)

- `GET /api/session/current` **and** `GET /api/sessions/current` return the **same** object,
  containing the union of all fields both callers read: `title, status, date, start, startTime,
  end, endTime, currentSpeaker, currentPoint, schedule, zoContent`. One handler, two routes.
- `GET /api/auth/me` returns the **bare** user `{id,username,name,role,club,permissions}`;
  `GET /api/current-user` returns the **same** user wrapped as `{ "user": <User> }`.

## C7. Parliamentarian upsert (spec §6.1.7, §8.5)

`POST /api/parliamentarians` (#30) is an **upsert**: if the body carries an `id` of an existing
parliamentarian → update it; otherwise create. Also implement `PUT /api/parliamentarians/:id`
(#31) for correctness. This keeps today's FE (which only POSTs for edits) working.

## C8. recipientsType normalization (spec §6.1.6)

`recipientsType ∈ {all, groups, members}`. Map incoming `"individual" → "members"` on write.
Eligibility resolution for a voting:
- `all` → every `User` (the voter collection),
- `groups` → users whose `group` ∈ `selectedGroups`,
- `members` → users whose id ∈ `selectedMembers`.

## C9. Two person collections (spec §2 Relacje) — keep separate

`User` (login/authors/managers/voters; `GET /users`, `GET /members`) and `Parliamentarian`
(chamber registry with clubs; `GET /parliamentarians`) are **distinct tables**. Do not join or
sync them in v1. Voting eligibility uses `User`; the parliamentarian registry is independent.

## C10. Response envelopes / wrapper keys (spec §3, §4)

The FE reads exact shapes — match them precisely. Non-obvious ones:
- `GET /api/resolutions` → `{ "resolutions": [...] }` (also include `session` key when known; FE
  tolerates extra keys).
- `GET /api/resolutions/:slug` → `{ resolution, signedUsers, session, currentUser }`
  (`currentUser` only when identity known).
- `GET /api/resolutions/session/:sessionId` → `{ resolutions, sessionId, count }`.
- `GET /api/resolutions/:x/amendments` → `{ resolution:{title,slug}, session:{city,date}, amendments:[...] }`.
- `GET /api/amendments/:id` → `{ "data": { ...amendment, resolution:{id,title,slug} } }`.
- `GET /api/parliamentarians` → `{ parliamentarians:[...clubId!=null], unaffiliated:[...clubId==null] }`.
- `GET /api/votings` and `GET /api/amendments` and `GET /api/clubs` and `GET /api/sessions` and
  `GET /api/speakers` and `GET /api/groups` and `GET /api/members` and `GET /api/users` → **bare
  arrays**.
- Mutations commonly return `{ "success": true, ... }` and/or the affected object — see each doc.

## C11. Polish error-message catalog

Return these strings verbatim in `{ "message": <...> }` (the FE displays `data.message`):

| Situation | Message |
|---|---|
| Bad login | `Nieprawidłowy login lub hasło` |
| Not authenticated (generic) | `Wymagane uwierzytelnienie` |
| No permission | `Brak uprawnień` |
| Voting not found | `Nie znaleziono głosowania` |
| Already voted | `Użytkownik już oddał głos` |
| Resolution not found | `Nie znaleziono uchwały` |
| Already signed | `Już podpisałeś tę uchwałę` |
| Author cannot remove signature | `Autor nie może usunąć podpisu` |
| Signature removed | `Podpis został usunięty` |
| Amendment not found | `Nie znaleziono poprawki` |
| No active session (if 404 chosen) | `Brak aktywnego posiedzenia` |

## C12. Slug generation (spec §4 #19)

`slugify(title)`: lowercase, spaces → `-`, strip characters not matching `[\w-]` (unicode word
chars OK for Polish). On collision append `-2`, `-3`, … Keep deterministic and stored on the row.

## C13. Timestamps & formats

- `createdAt` for resolutions/amendments is a **date** string `YYYY-MM-DD` (spec examples).
- `timestamp` on signatures is **ISO 8601** datetime.
- Voting `startTime`/`endTime` are ISO 8601; the FE also sends `datetime-local` on create — parse
  leniently (accept both `YYYY-MM-DDTHH:MM` and full ISO).
- Store timestamps as UTC; serialize in the format the FE expects per field.

## C14. Dev-setup expectations (spec §7) — reflected in `00-project-setup.md`

- Backend + Socket.IO on **`http://localhost:4000`**.
- Serve uploaded resolution files under **`/uploads/resolutions/<fileName>`** (FE fallback when
  `resolution.filePath` absent). Also set `filePath` on the model when known.
- CORS: allow origin `http://localhost:5173` (Vite dev) with `Authorization`, `Content-Type`
  headers + preflight — needed only when the FE bypasses the Vite proxy; enable it anyway.
- Accept `multipart/form-data` on #15 (voting attachments) and #19 (resolution docx).

## C15. Voting status rule (spec §2 Voting)

Persist `status`; authoritatively set `archived` (on #14) and `active` (on #13). The FE derives
`upcoming/active/finished` locally from `startTime/endTime` but reads `archived` from the stored
field — so always store an accurate `status` and never silently overwrite `archived`.
