# plan_steps — implementation briefs for mparlament-backend

These documents are **build briefs**. Each one is self-contained enough that an implementing
agent can build that vertical slice (domain → persistence → application → API → tests) from the
doc alone, guided by `../BACKEND_SPEC.md` (the frontend contract, the source of truth).

## How to use these docs

1. Read `CONVENTIONS.md` first — it resolves every cross-cutting ambiguity in the spec (auth
   header, optional-auth, abstain enum, polymorphic params, path aliases, permission matrix,
   Polish error-message catalog). Every feature doc links back to it.
2. Build in the order below. Each feature doc follows the **same template** (see below).
3. Work **test-first** (TDD): write the failing test listed in the doc's TDD checklist, then the
   code to make it pass. Order within a slice: domain unit → application → API integration.

## Architecture in one paragraph

**Vertical slices + DDD layering.** Each feature is a bounded context under
`src/mparlament/slices/<slice>/` owning four layers: `domain` (framework-free dataclass entities +
value objects + repository *ports*), `application` (use cases + Pydantic in/out DTOs),
`infrastructure` (SQLAlchemy models + repository adapters + mappers), `api` (FastAPI router +
request/response schemas). Dependencies point inward: `api → application → domain`;
`infrastructure` implements `domain` ports; `domain` depends on nothing. Cross-cutting concerns
live in `src/mparlament/shared/` (the shared kernel). SOLID/KISS/YAGNI throughout — no
speculative abstraction beyond what the spec's endpoints require.

## Recommended build order

| Step | Doc | Why here |
|---|---|---|
| 1 | `00-project-setup.md` | Poetry, skeleton, config, async DB, Alembic, app factory, pytest harness. |
| 2 | `01-shared-kernel.md` | Base classes, error handling, auth (tolerant Bearer, JWT, RBAC), storage port. |
| 3 | `CONVENTIONS.md` | Reference — read before every feature (not "built", but decisions are enforced in code). |
| 4 | `02-auth-identity.md` | Everything authed depends on login + `/me`. |
| 5 | `03-users.md` | Tiny; unlocks voting recipient/manager selection. |
| 6 | `04-sessions.md` | Independent. |
| 7 | `05-votings.md` | Largest; references resolutions/amendments as *linked items* (loose coupling by id). |
| 8 | `06-resolutions.md` | Referenced by votings + amendments. |
| 9 | `07-amendments.md` | Depends on resolutions (parent). |
| 10 | `08-parliamentarians-clubs.md` | Independent registry. |
| 11 | `09-groups-members.md` | Thin; supports voting recipients. |
| 12 | `10-realtime-deferred.md` | **Not implemented in v1** — REST + FE polling covers live voting. Build after REST is green. |

Votings/resolutions/amendments cross-reference only by `(linkedItemType, linkedItemId)` and
`resolutionId` — plain foreign keys, no hard module coupling. They can be built in any order as
long as the linked-item lookups degrade gracefully when the target does not yet exist.

## Endpoint coverage map (spec §3, #1–#43)

| # | Method Path | Doc |
|---|---|---|
| 1 | POST /api/auth/login | 02 |
| 2, 2b | GET /api/auth/me | 02 |
| 3 | GET /api/current-user | 02 |
| 4 | GET /api/session/current | 04 |
| 5 | PUT /api/session/current | 04 |
| 6 | GET /api/sessions/current | 04 |
| 7 | GET /api/sessions | 04 |
| 8 | GET /api/votings | 05 |
| 9 | GET /api/votings/:id | 05 |
| 10 | POST /api/votings | 05 |
| 11 | PUT /api/votings/:id | 05 |
| 12 | POST /api/votings/:id/vote | 05 |
| 13 | POST /api/votings/:id/activate | 05 |
| 14 | POST /api/votings/:id/archive | 05 |
| 15 | POST /api/votings/:id/attachments | 05 |
| 16 | DELETE /api/votings/:id | 05 |
| 17 | GET /api/resolutions | 06 |
| 18, 18b | GET /api/resolutions/:slug | 06 |
| 19 | POST /api/resolutions | 06 |
| 20 | GET /api/resolutions/session/:sessionId | 06 |
| 21 | POST /api/resolutions/:id/sign | 06 |
| 22 | DELETE /api/resolutions/:id/sign | 06 |
| 23, 23b | GET /api/resolutions/:slug/amendments | 07 |
| 24 | POST /api/resolutions/:slug/amendments | 07 |
| 25 | GET /api/resolutions/:slug/amendments/:amendmentId | 07 |
| 26 | GET /api/amendments | 07 |
| 27 | GET /api/amendments/:id | 07 |
| 28 | POST /api/amendments/:id/withdraw | 07 |
| 29 | GET /api/parliamentarians | 08 |
| 30 | POST /api/parliamentarians | 08 |
| 31 | PUT /api/parliamentarians/:id | 08 |
| 32 | DELETE /api/parliamentarians/:id | 08 |
| 33 | GET /api/clubs | 08 |
| 34 | POST /api/clubs | 08 |
| 35 | PUT /api/clubs/:id | 08 |
| 36 | DELETE /api/clubs/:id | 08 |
| 37, 38 | POST/DELETE /api/clubs/:id/members[/:memberId] | 08 |
| 39 | GET /api/speakers | 04 |
| 40 | POST /api/speakers | 04 |
| 41 | GET /api/groups | 09 |
| 42 | GET /api/members | 03 |
| 43 | GET /api/users | 03 |

Realtime events (spec §5) → `10-realtime-deferred.md`.

## Feature-doc template (every `NN-*.md` follows this)

1. **Context & spec refs** — endpoint numbers + which spec sections apply.
2. **Domain model** — dataclass entities, value objects, invariants, repository ports.
3. **Persistence** — SQLAlchemy models, migration notes, seed data.
4. **Application** — use cases (commands/queries) + Pydantic in/out DTOs.
5. **API** — routes with request/response shapes copied verbatim from the spec (wrapper keys,
   Polish messages, status codes, auth column).
6. **Cross-cutting conventions applied** — which `CONVENTIONS.md` rules bite here.
7. **TDD checklist** — ordered, red-first, with concrete assertions + example payloads.
8. **Definition of done.**
