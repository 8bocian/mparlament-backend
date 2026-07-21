# 04 — Sessions slice (posiedzenia)

## Context & spec refs

The live parliamentary sitting + the session list + speakers. Endpoints #4, #5, #6, #7, #39, #40.
Spec §2 (Session, CurrentSession, Speaker), §4 (SESSIONS, SPEAKERS), §6.1.1 (dual path aliases);
`CONVENTIONS.md` C3 (admin/marshal), C6 (aliases + superset), C10, C13 (dates).

## Domain model (`slices/sessions/domain/`)

**`Session`** (list item / stored sitting):
```
id: int
name: str
date: str          # display date, e.g. "19.09.2026"
city: str
number: str | None       # FE fallback fields (optional)
start: str | None
startTime: str | None
end: str | None
endTime: str | None
```

**`CurrentSession`** aggregate — the "na żywo" object; superset per C6:
```
id, title, status,          # status e.g. "TRWA"
active: bool,
date, start, startTime, end, endTime,
currentSpeaker: Speaker | None,   # { name, club, role, time }
currentPoint: AgendaPoint | None, # { number, title, type }
schedule: list[ScheduleItem],     # { time, title, status }  status∈done|active|waiting|crossed|disabled
zoContent: str                    # "ZO" mode text
```
Value objects (frozen dataclasses): `Speaker{name, club, role, time?}`,
`AgendaPoint{number, title, type}`, `ScheduleItem{time, title, status}`.

**`Speaker`** registry entity (for #39/#40): `{ id, name, club, role }`.

Invariants: `schedule` item `status` from the allowed set; partial `PUT` merges (see below).
Ports: `CurrentSessionRepository` (`get`, `save`), `SessionRepository` (`list_all`),
`SpeakerRepository` (`list_all`, `add`).

Design note: v1 has a single "current session" row (the FE only ever reads *the* current one).
Model it as a singleton row (id=1) or the most-recent active session. KISS.

## Persistence (`infrastructure/`)

- `sessions` table for the list (#7) and to back the current session's scalar fields.
- Current-session complex fields (`currentSpeaker`, `currentPoint`, `schedule`, `zoContent`)
  stored as JSON columns on the current-session row (SQLite `JSON`). This avoids premature
  normalization (YAGNI) while matching the FE's document-shaped reads/writes.
- `speakers` table `{id, name, club, role}`.
- Seed: one current session (`status="TRWA"`, a `schedule`, a `currentSpeaker`, `zoContent`),
  a few `sessions` list rows, a couple speakers.

## Application (`application/`)

- `GetCurrentSessionUseCase.execute() -> CurrentSessionDTO` (superset payload).
- `UpdateCurrentSessionUseCase.execute(patch: dict, actor: User) -> CurrentSessionDTO` — **partial
  merge**: FE sends `{schedule}` **or** `{currentPoint, zoContent}` (or other subsets). Only
  overwrite provided keys; leave others intact. RBAC admin/marshal (C3).
- `ListSessionsUseCase.execute() -> list[SessionListDTO]`.
- `ListSpeakersUseCase` / `AddSpeakerUseCase.execute(name, club, role) -> SpeakerDTO`.
- DTOs mirror the domain shapes; `CurrentSessionDTO` serializes **all** superset fields.

## API (`api/router.py`) — routes under `/api`

### #4 `GET /api/session/current` (Bearer) AND #6 `GET /api/sessions/current` (Bearer)
- **Two routes, one handler** (C6). 200 → the superset `CurrentSession` object with `title,
  status, date, start, startTime, end, endTime, currentSpeaker, currentPoint, schedule, zoContent`.
- If no active session: return the object anyway (mock never 404s). Optionally support 404
  `{message:"Brak aktywnego posiedzenia"}` behind a flag, but default to always-return-object to
  match the FE.

### #5 `PUT /api/session/current` (Bearer, admin/marshal)
- Body: **partial** session object. 200 → updated full object (`setSession(data)` on FE).

### #7 `GET /api/sessions` (public)
- 200 → **bare array** `[{ id, name, date, city }]`.

### #39 `GET /api/speakers` (Bearer)
- 200 → bare array `[{ name, club, role }]`.

### #40 `POST /api/speakers` (Bearer, admin/marshal)
- Body `{ name, club, role }`. 200/201 → `{ id, name, club, role }` (FE appends to list).

## Cross-cutting conventions applied

C6 (both aliases return superset; one handler), C3 (admin/marshal on `PUT` + `POST /speakers`),
C10 (bare arrays for #7/#39), C13 (keep FE date formats verbatim).

## TDD checklist (red-first)

1. **`test_get_current_session_superset`** — authed GET `/api/session/current` → 200 containing
   **all** superset keys; `schedule` items have `time,title,status`.
2. **`test_sessions_current_alias_identical`** — `/api/sessions/current` returns the same object
   as `/api/session/current`.
3. **`test_put_session_partial_schedule`** — PUT `{schedule:[...]}` updates schedule, leaves
   `zoContent` unchanged; returns full object.
4. **`test_put_session_partial_point_and_zo`** — PUT `{currentPoint, zoContent}` updates only those.
5. **`test_put_session_requires_admin_or_marshal`** — plain member → 403 `Brak uprawnień`.
6. **`test_list_sessions_shape`** — public GET → bare array `[{id,name,date,city}]`.
7. **`test_speakers_get_and_post`** — POST `{name,club,role}` → 201 with `id`; subsequent GET
   includes it; POST requires admin/marshal.

## Definition of done

- Both current-session paths return the identical superset object; partial PUT merges correctly.
- `/api/sessions` + `/api/speakers` shapes exact; RBAC enforced on writes.
- Note in code: realtime broadcasts (`scheduleUpdated`, `speakerUpdated`, `zoContentUpdated`) are
  **hooks left for doc 10** — the PUT/POST handlers should be structured so emitting an event
  later is a one-line addition (leave a TODO, do not implement Socket.IO now — YAGNI).
