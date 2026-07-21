# 06 — Resolutions slice (uchwały)

## Context & spec refs

Resolution documents (chapters/articles), docx upload, signatures, slug/id polymorphism.
Endpoints #17, #18, #18b, #19, #20, #21, #22. Spec §2 (Resolution, ResolutionSignature), §4
(RESOLUTIONS), §4.0; `CONVENTIONS.md` C2 (identity w/o token), C5 (polymorphic slug/id), C10
(wrappers), C11, C12 (slug), C13 (dates), C14 (uploads/static).

## Domain model (`slices/resolutions/domain/`)

**`Resolution`** aggregate:
```
id: int
title: str
slug: str
fileName: str | None
authorId: int
author: str
party: str | None
sessionId: int | None
preamble: str | None
chapters: list[Chapter]      # Chapter{ id, title, articles:[Article{id,number,content}] }
signatures: int              # count (derived or maintained)
status: str                  # pending|accepted|rejected
createdAt: str               # "YYYY-MM-DD" (C13)
filePath: str | None         # URL; FE fallbacks to /uploads/resolutions/<fileName>
```
Value objects: `Chapter{id,title,articles}`, `Article{id,number,content}`.

**`ResolutionSignature`** entity:
`{ id, resolutionId, userId, timestamp (ISO), type: "signature"|"author" }`.
Invariants: author is auto-signed on create (`type="author"`) and **cannot** remove their
signature (C11 message). A user may sign once (`ConflictError("Już podpisałeś tę uchwałę")`).

Domain services:
- `slugify(title)` per C12 (collision-safe).
- `sign(user)` / `unsign(user)` with author-protection.
- `signatures` = count of signature rows (keep the scalar in sync or compute).

Ports: `ResolutionRepository` (`get_by_id`, `get_by_slug`, `list_all`, `list_by_session`, `add`,
`update`), `SignatureRepository` (`add`, `remove`, `list_by_resolution`, `get`). Plus a
`resolve_resolution(param, repo)` shared helper (C5).

## Persistence (`infrastructure/`)

- `resolutions` table; `chapters`/`articles` stored as JSON on the row (document-shaped; matches
  FE reads/writes; avoids over-normalization — KISS/YAGNI). `slug` unique index.
- `resolution_signatures` table `{id, resolution_id FK, user_id FK, timestamp, type}`, unique
  `(resolution_id, user_id)`.
- Uploaded `.docx` saved via `FileStorage` under `resolutions/`; `filePath` set to
  `/uploads/resolutions/<fileName>` (C14).
- Seed: 1–2 resolutions with chapters, `status="pending"`, author auto-signature.

## Application (`application/`)

- `ListResolutionsUseCase` → `{ resolutions: [...] }` (+ `session` key if known — C10).
- `GetResolutionUseCase.execute(param, requester?) -> {resolution, signedUsers, session,
  currentUser?}` — `param` polymorphic (C5); `currentUser` only when identity known (C2).
- `CreateResolutionUseCase.execute(file_bytes, fileName, data_json, ...)` — parse the `data` JSON
  string (title, chapters, preamble?, fileName, author, authorId, party, sessionId); generate
  `slug` (C12); `status="pending"`; `signatures=1`; `createdAt=today`; save file; create author
  auto-signature. Return the created Resolution.
- `SignResolutionUseCase.execute(id, user)` / `UnsignResolutionUseCase.execute(id, user)` —
  identity via C2 chain; author-protection on unsign.
- `ListSessionResolutionsUseCase.execute(sessionId) -> {resolutions, sessionId, count}`.
- DTOs mirror shapes; `SignedUser{ name, club, timestamp, type }`;
  `CurrentUserBlock{ hasSigned, isAuthor, signatureType, isAutoSigned }`.

## API (`api/router.py`) — under `/api`

### #17 `GET /api/resolutions` (optional auth — sometimes Bearer, sometimes none, C2)
- 200 → `{ "resolutions": [ <Resolution> ] }` (include `session` too if available — C10).

### #18 / #18b `GET /api/resolutions/:slug` (public / Bearer; slug **or** id — C5)
- 200 →
  ```json
  { "resolution": {..., "chapters":[...]},
    "signedUsers": [{"name","club","timestamp","type"}],
    "session": {"city","date"},
    "currentUser": {"hasSigned","isAuthor","signatureType","isAutoSigned"} }
  ```
  `currentUser` only when identity known. 404 → `{message:"Nie znaleziono uchwały"}`.

### #19 `POST /api/resolutions` (public, multipart via XHR — C14)
- `multipart/form-data`: `file` (`.docx`) + `data` (**JSON string**). 201 → created Resolution
  (`slug`, `status:"pending"`, `signatures:1`, `createdAt`). Error → non-2xx `{message}`.

### #20 `GET /api/resolutions/session/:sessionId` (public)
- 200 → `{ resolutions:[...], sessionId, count }`.

### #21 `POST /api/resolutions/:id/sign` (public; identity via C2)
- No body. 200 → `{ success: true }`. 400 → `{message:"Już podpisałeś tę uchwałę"}`. FE refreshes #18.

### #22 `DELETE /api/resolutions/:id/sign` (public; identity via C2)
- 200 → `{ success:true, message:"Podpis został usunięty" }`. 403 →
  `{message:"Autor nie może usunąć podpisu"}`; 404 when no signature.

## Cross-cutting conventions applied

C2 (sign/unsign identity chain; optional auth reads), C5 (slug-or-id), C10 (wrappers), C11
(messages), C12 (slug gen), C13 (`createdAt` date, signature ISO timestamp), C14 (docx storage +
`filePath`/static serving).

## TDD checklist (red-first)

1. **`test_slugify`** — Polish title → lowercase, spaces→`-`, stripped; collision → `-2`.
2. **`test_list_resolutions_wrapper`** — GET → `{resolutions:[...]}` (array under key).
3. **`test_get_by_slug_shape`** — GET by slug → `{resolution,signedUsers,session}`; `resolution`
   has `chapters`.
4. **`test_get_by_numeric_id_polymorphic`** — `GET /api/resolutions/<id>` (numeric) resolves by id
   (C5), same shape (used by VotingPage #18b).
5. **`test_get_404`** — unknown → `{message:"Nie znaleziono uchwały"}`.
6. **`test_currentUser_block_present_when_authed`** — with token, response has `currentUser` with
   `hasSigned/isAuthor/signatureType/isAutoSigned`; absent when anonymous.
7. **`test_create_multipart`** — POST `file` + `data`(JSON string) → 201; `slug` generated,
   `status="pending"`, `signatures==1`, `createdAt` is `YYYY-MM-DD`; author auto-signature exists
   (`type="author"`); file saved and `filePath`/`/uploads/resolutions/<fileName>` serves it.
8. **`test_sign_and_refresh`** — a member signs → 200 `{success:true}`; appears in `signedUsers`;
   `signatures` incremented.
9. **`test_sign_twice_conflict`** — → 400 `Już podpisałeś tę uchwałę`.
10. **`test_unsign_author_forbidden`** — author DELETE own signature → 403 `Autor nie może usunąć
    podpisu`.
11. **`test_unsign_member_ok`** — non-author signer removes → 200 `{success:true, message:"Podpis
    został usunięty"}`.
12. **`test_session_resolutions_shape`** — `{resolutions,sessionId,count}`.

## Definition of done

- Multipart create works with the `file`+`data`-JSON-string contract; slug/id polymorphism works;
  author auto-sign + author-protected unsign enforced; wrappers + Polish messages exact.
- Uploaded docx served at `/uploads/resolutions/<fileName>`; `filePath` populated.
- `LinkedItemStatusUpdater` (used by votings #14) can flip a resolution's `status` to
  accepted/rejected — expose the repo method needed.
