# 10 — Realtime (Socket.IO) — DEFERRED, NOT IMPLEMENTED IN v1

> **Status: PLAN ONLY.** Do **not** implement in the first pass. The REST endpoints + the
> frontend's built-in **3-second polling** of `GET /api/votings/:id` (spec §5) cover live voting
> for v1. Build this only after the REST slices are green. `python-socketio` is intentionally
> **not** added to dependencies yet (YAGNI).

## Context & spec refs

Spec §5 (Realtime) is the source of truth — **the frontend code wins** over `API.md`. The FE uses
**Socket.IO client v4**, but the whole `SocketProvider.jsx` layer is currently **commented out**
(`socket === null`), so nothing emits today. This doc captures the target contract to switch on
later. `CONVENTIONS.md` C14 (port 4000).

## Target transport

- **Socket.IO** (not raw WebSocket) on **`http://localhost:4000`** — same host as the API; FE
  hardcodes this URL. `io(SOCKET_URL, { transports:["websocket"], autoConnect:true })`.
- Configure Socket.IO server CORS for the FE origin (`http://localhost:5173`).
- Connection-state events the FE listens for: `connect`, `disconnect`, `connect_error`.
- Python: add `python-socketio` (ASGI mode) and mount it alongside FastAPI (e.g. `socketio.ASGIApp`
  wrapping the FastAPI app, or a combined ASGI app), sharing port 4000.

## Events (source of truth = FE listeners; API.md is wrong — ignore its `VOTE_UPDATE`/`ws://` form)

| Event | Dir | Payload | Emitted when |
|---|---|---|---|
| `voteUpdate:<votingId>` | S→C | `{ votedCount, votesFor, votesAgainst, abstained, votedUsers[], notVotedUsers[] }` | after each vote cast on that voting (event name embeds the voting id) |
| `zoContentUpdated` | S→C **and** C→S | `zoContent` (string) | admin edits ZO mode text; server rebroadcasts to all |
| `scheduleUpdated` | S→C | `newSchedule` (schedule array) | session schedule changes |
| `speakerUpdated` | S→C | `newSpeaker` `{ name, club, role, time }` | current speaker changes |

**Field names must match exactly** (`votesFor`, not `for`; `votedCount`, not `voted`). These are
the same fields `GET /api/votings/:id` already returns (doc 05) — reuse the votings query service
to build the payload so REST and socket stay in parity.

## Emission hook points (left as TODOs in the REST slices)

- Votings `CastVoteUseCase` (doc 05) → emit `voteUpdate:<id>` after commit.
- Sessions `UpdateCurrentSessionUseCase` (doc 04) → emit `scheduleUpdated` / `speakerUpdated` /
  `zoContentUpdated` depending on which keys changed; also handle the inbound `zoContentUpdated`
  (C→S) by persisting + rebroadcasting.

Structure the v1 REST use cases so emitting is a single added call (inject an optional
`EventPublisher` port that is a no-op in v1). This keeps the door open without coupling.

## Fallback parity requirement (already satisfied by v1 REST)

`LiveVoting` polls `GET /api/votings/:id` every 3s when `!isConnected`, reading the same fields as
`voteUpdate`. So doc 05 must return `votedCount, votesFor, votesAgainst, abstained, votedUsers,
notVotedUsers` — verified there. **No socket needed for correctness**, only for latency.

## TDD checklist (when implemented later)

1. Client connects to `:4000`, receives `connect`.
2. Casting a vote (REST) emits `voteUpdate:<id>` with the exact field names/counts.
3. `zoContentUpdated` round-trips C→S→all-clients and persists.
4. `scheduleUpdated` / `speakerUpdated` fire on session PUT.
5. Payloads equal the corresponding `GET /api/votings/:id` fields (REST/socket parity).

## Definition of done (deferred)

- Not required for v1 sign-off. When built: `python-socketio` mounted on 4000 with CORS; the four
  events emit with exact payloads; parity test with REST passes; FE `SocketProvider` can be
  uncommented and works.
