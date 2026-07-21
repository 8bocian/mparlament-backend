# BACKEND_SPEC.md — Specyfikacja kontraktu API (Parlament Młodych RP)

> Dokument wygenerowany na podstawie analizy kodu frontendu. **Źródłem prawdy jest kod
> frontendu** (`src/**`), a nie istniejąca dokumentacja `API.md` — rozbieżności między nimi
> opisano w sekcji 6. Backend należy zbudować tak, aby ten frontend działał bez zmian
> (poza świadomie zaakceptowanymi poprawkami z sekcji 8).

---

## 1. Rozpoznanie

### 1.1. Stack frontendu
- **Framework:** React 19 + React Router DOM 7 (`HashRouter` — routing po `#`, więc backend nie
  obsługuje ścieżek SPA, całość serwowana jako statyk).
- **Bundler/dev server:** Vite 8.
- **Brak TypeScript** (czysty JSX).
- Biblioteki pomocnicze (klientowe, nieistotne dla API): `docx`, `docx-templates`,
  `docxtemplater`, `mammoth`, `jszip`, `fast-xml-parser`, `file-saver` — służą do **lokalnego**
  parsowania i generowania plików `.docx` w przeglądarce (patrz `src/utils/docx*.js`,
  `utils/ResolutionFinalizer.js`). Backend **nie** uczestniczy w generowaniu docx.

### 1.2. Sposób komunikacji z serwerem
- **HTTP: natywny `fetch`** (brak axios). Jeden wyjątek: `SubmitResolution.jsx` używa
  **`XMLHttpRequest`** (dla paska postępu uploadu) do `POST /api/resolutions`.
- **Realtime: `socket.io-client` v4** (`src/socket/SocketProvider.jsx`) — **obecnie w całości
  zakomentowany**, `socket === null`, więc realtime faktycznie nie działa. Kod nasłuchujący
  eventy istnieje w komponentach (patrz sekcja 5). Docelowy URL z kodu: `http://localhost:4000`.
- Wszystkie ścieżki HTTP są **względne** (`/api/...`) — brak zmiennych `import.meta.env`/`VITE_*`,
  brak stałej `API_URL`/`BASE_URL`. Oznacza to, że w produkcji API musi być pod tym samym
  originem co frontend (lub przez reverse-proxy), a w dev — przez proxy Vite (patrz sekcja 7).
- Format ciała: JSON (`Content-Type: application/json`) oraz `multipart/form-data` dla uploadu
  plików (uchwały, załączniki głosowań).

### 1.3. Znaleziona dokumentacja
- **`API.md`** (w katalogu głównym) — obszerna, ręcznie pisana dokumentacja API. Traktowana
  **pomocniczo**. W wielu miejscach rozjeżdża się z kodem (patrz sekcja 6).
- **MSW (`src/mocks/`)** — pełny mock backendu (Mock Service Worker). To najbliższy „działający
  kontrakt": `src/mocks/handlers.js` definiuje odpowiedzi dla realnie wołanych endpointów, a
  `src/mocks/data/*` — dane przykładowe. **MSW jest de facto referencyjną implementacją** i był
  używany do rozstrzygania kształtu odpowiedzi. Uwaga: MSW też bywa niespójny z API.md.
- `README.md` — szablonowy (Vite), bez wartości.
- Brak plików `.http`/`.rest`, brak kolekcji Postmana, brak katalogu `docs/`.

### 1.4. Uwierzytelnianie — jak działa w kodzie (WAŻNE)
- Po `POST /api/auth/login` frontend zapisuje do `localStorage`:
  - `token` = `JSON.stringify({ token: <jwt>, expiresAt: <ms> })` (TTL 10 h),
  - `user` = `JSON.stringify(<user>)`.
- Przy requestach autoryzowanych wysyła nagłówek:
  ```js
  const token = localStorage.getItem("token");        // to jest CAŁY JSON, nie sam JWT!
  headers: { Authorization: `Bearer ${token}` }
  ```
  **➜ Nagłówek `Authorization` zawiera `Bearer {"token":"...","expiresAt":...}`, a nie sam JWT.**
  To błąd frontendu (sekcja 6/8). Backend musi to uwzględnić: albo parsować JSON z bearera,
  albo — rekomendowane — poprosić o poprawkę FE, by wysyłał `parsed.token`.
- `ProtectedRoute` sprawdza jedynie *obecność* klucza `token` w `localStorage` (nie waliduje go).
- **Część endpointów wołana jest BEZ nagłówka `Authorization`** — patrz sekcja 4.0 i kolumna
  „auth" w tabeli (sekcja 3).

---

## 2. Modele danych (wyprowadzone z payloadów)

Typy orientacyjne (JS). Pola oznaczone „(computed)" backend wylicza przy odczycie.

### User
| pole | typ | uwagi |
|---|---|---|
| id | int | |
| username | string | login, np. `TEST123` |
| password | string | **nigdy nie zwracać w odpowiedziach** (mock niestety zwraca w `GET /api/users`) |
| name | string | „Jan Kowalski" |
| club | string | nazwa klubu tekstem (np. „TEST"); używane przez FE jako `party`/`club` |
| role | enum | `admin` \| `marshal` \| `member` |
| permissions | string[] | `MANAGE_VOTINGS`, `MANAGE_RESOLUTIONS`, `MANAGE_PARLIAMENTARIANS` |

### Session (pozycja listy) — `GET /api/sessions`
`{ id, name, date, city }`. FE (Finalize) czyta też opcjonalnie `number`, `startDate`, `location`
jako fallback — można pominąć.

### CurrentSession — posiedzenie „na żywo"
Jeden obiekt obsługujący **dwa różne kształty odczytu** (rozbieżność, sekcja 6):
```
{
  id, title,
  status,                 // "TRWA" | ...  (czytane przez SessionDetails)
  active,                 // bool          (obecne w mocku, nieczytane wprost)
  date,                   // "19.09.2026"  (SessionDetails)
  start, startTime, end, endTime,          // (Dashboard: /api/sessions/current)
  currentSpeaker: { name, club, role, time },
  currentPoint:   { number, title, type },
  schedule: [ { time, title, status } ],   // status: done|active|waiting|crossed|disabled
  zoContent: string       // treść trybu „ZO" (Zespół Organizacyjny)
}
```

### Voting
Pola zapisywane/edytowane przez FE:
```
id, title, description,
category,               // resolution|amendment|law|budget|committee|other
startTime, endTime,     // ISO 8601
status,                 // active|finished|upcoming|archived  (patrz reguła statusu niżej)
recipientsType,         // all|groups|members   (FE bywa też "individual" — mapować na members)
selectedGroups: int[],
selectedMembers: int[],
linkedItemType,         // none|resolution|amendment
linkedItemId,           // string lub int (uchwała po ID; poprawka po ID)
applicant,              // marshal|presidium|group_15|individual  lub  id grupy (string)
managers: int[],        // userId osób mogących zarządzać głosowaniem
attachments: [ { id, name, size, type, uploadDate } ],
createdBy,              // string (nazwa autora)
// pola opcji z formularza tworzenia (FE wysyła, ale ich nie odczytuje z odpowiedzi):
quorumRequired, majorityType, allowAbstain, isAnonymous, requireComment,
canChangeVote, showResultsDuringVoting, notifyEmail, notifyPush
```
Pola **wyliczane przy odczycie** (computed):
```
votesFor, votesAgainst, abstained,        // liczniki głosów
votedCount, totalEligible,                // frekwencja
eligibleUsers: [ { id, name, club } ],
votedUsers:    [ { id, name, club } ],
notVotedUsers: [ { id, name, club } ],
hasVoted: bool, myVote: "for"|"against"|"abstain"|null   // dla bieżącego usera
```
> Uwaga o statusie: `VotingList`/`VotingPage` **wyliczają status lokalnie** z `startTime`/`endTime`
> (`upcoming`/`active`/`finished`), a `archived` biorą z pola `status`. Backend powinien
> przechowywać `status` (zwłaszcza `archived`) i ustawiać go przy `activate`/`archive`.

### Vote (głos pojedynczej osoby)
`{ votingId: int, userId: int, vote: "for"|"against"|"abstained" }`.
> ⚠️ Enum niespójny z FE: przycisk w `VotingPage` wysyła `"abstain"`, a liczenie po stronie
> mocka filtruje `"abstained"`. Backend musi ujednolicić (sekcja 6/8).

### Resolution (uchwała)
```
id, title, slug, fileName,
authorId, author, party,
sessionId,
preamble,
chapters: [ { id, title, articles: [ { id, number, content } ] } ],
signatures: int,          // liczba podpisów
status,                   // pending|accepted|rejected
createdAt,                // "2026-07-09"
filePath?                 // opcjonalny URL do pliku; FE fallbackuje na /uploads/resolutions/<fileName>
```

### ResolutionSignature
`{ id, resolutionId, userId, timestamp (ISO), type: "signature"|"author" }`.
Autor uchwały jest podpisany automatycznie (`type: "author"`, nie może usunąć podpisu).

### Amendment (poprawka)
```
id, resolutionId,
author, authorId, club,
content,                  // opis tekstowy
status,                   // pending|accepted|rejected|withdrawn
createdAt,
withdrawnReason,          // string|null
changes: [ { articleId, before, after, type? } ]
// type (z formularza AddAmendment): modify|add|delete
// konwencje wartości: before=null → nowy artykuł; after="(usunięty)" → usunięcie
```

### Parliamentarian
`{ id, firstName, lastName, clubId, clubName, clubColor, functions: string[], commissions: string[] }`.
`clubId=null` ⇒ niezrzeszony (`clubName`/`clubColor` = null).

### Club
`{ id, name, type: "klub"|"koło"|"komitet", color, members: [ { id, firstName, lastName, functions, commissions } ] }`.

### Speaker
`{ name, club, role }` (backend przy `POST` zwraca też `id`).

### Group
`{ id, name }` (+ opcjonalnie `memberCount` — FE wyświetla `group.memberCount || 0`).

### Member (do wyboru odbiorców głosowania)
`{ id, name, group }`.

### Relacje
- User 1—N Resolution (`authorId`), 1—N Amendment (`authorId`), 1—N Vote (`userId`),
  N—N Resolution przez ResolutionSignature.
- Resolution 1—N Amendment (`resolutionId`); Resolution N—1 Session (`sessionId`).
- Voting N—1 (opcjonalnie) Resolution/Amendment przez (`linkedItemType`,`linkedItemId`);
  Voting 1—N Vote.
- Parliamentarian N—1 Club (`clubId`).
- Uwaga: występują **dwie odrębne kolekcje osób** — `User` (logowanie, autorzy, managerowie,
  `GET /api/users`, `GET /api/members`) oraz `Parliamentarian` (rejestr izby, kluby). W obecnym
  froncie nie są spójnie połączone (patrz sekcja 6).

---

## 3. Tabela wszystkich endpointów

Legenda auth: **Bearer** = FE wysyła `Authorization` (choć malformowany, sekcja 1.4);
**BRAK** = FE nie wysyła nagłówka auth; **(handler-only)** = istnieje w mocku/API.md, ale
frontend go nie woła.

| # | Metoda | Ścieżka | Auth (jak woła FE) | Plik frontendu |
|---|---|---|---|---|
| 1 | POST | `/api/auth/login` | BRAK (login) | `authentication/pages/Login.jsx` |
| 2 | GET | `/api/auth/me` | Bearer | `VotingList`, `VotingDetailsPage`, `LiveVoting`, `EditVoting`, `SessionDetails`, `Parliamentarians`, `Dashboard` |
| 2b| GET | `/api/auth/me` | **BRAK** | `SubmitResolution.jsx`, `amendments/pages/AddAmendment.jsx` |
| 3 | GET | `/api/current-user` | BRAK | `amendments/pages/AmendmentsPage.jsx` |
| 4 | GET | `/api/session/current` | Bearer | `meetings/pages/SessionDetails.jsx` |
| 5 | PUT | `/api/session/current` | Bearer | `meetings/pages/SessionDetails.jsx` |
| 6 | GET | `/api/sessions/current` | Bearer | `dashboard/pages/Dashboard.jsx` |
| 7 | GET | `/api/sessions` | BRAK | `Resolutions`, `SubmitResolution`, `FinalizeResolution` |
| 8 | GET | `/api/votings` | Bearer (+`?userId=&role=`) | `voting/pages/VotingList.jsx` |
| 9 | GET | `/api/votings/:id` | Bearer | `VotingPage`, `VotingDetailsPage`, `LiveVoting`, `EditVoting` |
| 10 | POST | `/api/votings` | Bearer | `voting/pages/CreateVoting.jsx` |
| 11 | PUT | `/api/votings/:id` | Bearer | `voting/pages/EditVoting.jsx` |
| 12 | POST | `/api/votings/:id/vote` | Bearer | `voting/pages/VotingPage.jsx` |
| 13 | POST | `/api/votings/:id/activate` | Bearer | `voting/pages/VotingList.jsx` |
| 14 | POST | `/api/votings/:id/archive` | Bearer | `voting/pages/VotingList.jsx` |
| 15 | POST | `/api/votings/:id/attachments` | Bearer (multipart) | `CreateVoting`, `EditVoting` |
| 16 | DELETE | `/api/votings/:id` | (handler-only) | — |
| 17 | GET | `/api/resolutions` | Bearer / BRAK | `CreateVoting`,`EditVoting` (Bearer); `Resolutions.jsx` (BRAK) |
| 18 | GET | `/api/resolutions/:slug` | BRAK | `ResolutionDetails.jsx`, `AddAmendment.jsx` |
| 18b| GET | `/api/resolutions/:linkedItemId` | Bearer | `VotingPage.jsx` (**po ID, nie slug!**) |
| 19 | POST | `/api/resolutions` | **BRAK** (multipart/XHR) | `resolutions/pages/SubmitResolution.jsx` |
| 20 | GET | `/api/resolutions/session/:sessionId` | BRAK | `FinalizeResolution.jsx` |
| 21 | POST | `/api/resolutions/:id/sign` | BRAK | `ResolutionDetails.jsx` |
| 22 | DELETE | `/api/resolutions/:id/sign` | BRAK | `ResolutionDetails.jsx` |
| 23 | GET | `/api/resolutions/:slug/amendments` | BRAK | `AmendmentsPage.jsx` |
| 23b| GET | `/api/resolutions/:resolutionId/amendments` | BRAK | `FinalizeResolution.jsx` (**po ID, nie slug!**) |
| 24 | POST | `/api/resolutions/:slug/amendments` | BRAK | `amendments/pages/AddAmendment.jsx` |
| 25 | GET | `/api/resolutions/:slug/amendments/:amendmentId` | BRAK | `amendments/pages/AmendmentDetails.jsx` |
| 26 | GET | `/api/amendments` | Bearer | `CreateVoting`, `EditVoting` |
| 27 | GET | `/api/amendments/:id` | Bearer | `VotingPage.jsx` (linked item) |
| 28 | POST | `/api/amendments/:id/withdraw` | BRAK | `amendments/pages/AmendmentsPage.jsx` |
| 29 | GET | `/api/parliamentarians` | Bearer | `Parliamentarians.jsx`, `LiveVoting.jsx` |
| 30 | POST | `/api/parliamentarians` | Bearer | `Parliamentarians.jsx` (dodawanie **i** edycja!) |
| 31 | PUT | `/api/parliamentarians/:id` | (handler-only) | — |
| 32 | DELETE | `/api/parliamentarians/:id` | Bearer | `Parliamentarians.jsx` |
| 33 | GET | `/api/clubs` | Bearer | `Parliamentarians.jsx` |
| 34 | POST | `/api/clubs` | Bearer | `Parliamentarians.jsx` |
| 35 | PUT | `/api/clubs/:id` | Bearer | `Parliamentarians.jsx` |
| 36 | DELETE | `/api/clubs/:id` | Bearer | `Parliamentarians.jsx` |
| 37 | POST | `/api/clubs/:id/members` | (handler-only) | — |
| 38 | DELETE | `/api/clubs/:id/members/:memberId` | (handler-only) | — |
| 39 | GET | `/api/speakers` | Bearer | `SessionDetails.jsx` |
| 40 | POST | `/api/speakers` | Bearer | `SessionDetails.jsx` |
| 41 | GET | `/api/groups` | Bearer | `VotingDetailsPage`, `CreateVoting`, `EditVoting` |
| 42 | GET | `/api/members` | Bearer | `CreateVoting.jsx` |
| 43 | GET | `/api/users` | Bearer | `VotingDetailsPage`, `CreateVoting`, `EditVoting` |

---

## 4. Szczegóły endpointów

### 4.0. Endpointy publiczne (wołane BEZ `Authorization`)
Backend musi je udostępnić bez wymogu tokenu **albo** zaakceptować poprawkę FE (sekcja 8).
Lista: #1 login, #2b `/api/auth/me` (Submit/AddAmendment), #3 `/api/current-user`,
#7 `/api/sessions`, #17 `/api/resolutions` (z `Resolutions.jsx`), #18/#18b `/api/resolutions/:slug`,
#19 `POST /api/resolutions`, #20, #21, #22, #23/#23b, #24, #25, #28.
> Uwaga: te same zasoby bywają wołane raz z tokenem, raz bez (np. `/api/resolutions`,
> `/api/auth/me`). Najbezpieczniej: uczynić odczyty opcjonalnie-autoryzowanymi (token jeśli jest
> — personalizacja `currentUser`/`myVote`; brak tokenu — dane publiczne).

---

### AUTH

#### 1. `POST /api/auth/login`
- Auth: brak. Nagłówki: `Content-Type: application/json`.
- Body: `{ "username": string, "password": string }`.
- 200: `{ token: string, user: { id, username, name, role, permissions } }`.
  FE zapisuje `data.token` i `data.user` (czyta `id, name, role, permissions`; `club` dochodzi z `/me`).
- Błąd 401: `{ message: "Nieprawidłowy login lub hasło" }` (FE wyświetla `data.message`).

#### 2 / 2b. `GET /api/auth/me`
- Auth: zwykle Bearer; **bez tokenu** w `SubmitResolution` i `AddAmendment`.
- 200: pełny obiekt użytkownika `{ id, username, name, role, club, permissions }`.
  Odczytywane pola: `id`, `name`, `role`, `permissions`, `club`.
  Wyliczanie uprawnień w FE: `isAdmin = role==="admin" || permissions.includes("MANAGE_*")`.
- 401: `{ message }` — FE traktuje jako „niezalogowany" (ustawia `isAdmin=false` / redirect do `/zaloguj`).

#### 3. `GET /api/current-user`
- Auth: brak. Używane tylko przez `AmendmentsPage` do ustalenia autora poprawki.
- 200: `{ user: <User> }` (**opakowane w `user`** — inaczej niż `/api/auth/me`).
- 401: `{ message }`.

---

### SESSIONS

#### 4. `GET /api/session/current`
- Auth: Bearer. 200: obiekt CurrentSession (patrz model). Odczyt: `title, date, status,
  currentSpeaker, currentPoint, schedule, zoContent`.
- (Mock nie zwraca 404 przy braku sesji; API.md sugeruje `{ message: "Brak aktywnego posiedzenia" }`.)

#### 5. `PUT /api/session/current`
- Auth: Bearer + JSON. Rola: admin/marszałek (patrz sekcja `Autoryzacja`).
- Body: **częściowy** obiekt sesji, wysyłany różnie w zależności od akcji, m.in.:
  `{ schedule }`, albo `{ currentPoint, zoContent }`.
- 200: zaktualizowany obiekt sesji (FE robi `setSession(data)`).

#### 6. `GET /api/sessions/current`
- Auth: Bearer. Używane wyłącznie przez `Dashboard`. Odczyt: `title, start, startTime, end, endTime`.
- ⚠️ To **inna ścieżka** niż #4 (`/api/session/current`). Rekomendacja: sekcja 6/8.

#### 7. `GET /api/sessions`
- Auth: brak. 200: **tablica** `[{ id, name, date, city }]`.

---

### VOTING

#### 8. `GET /api/votings`
- Auth: Bearer. Query opcjonalne: `?userId=<id>&role=<role>` (FE dodaje je tylko dla nie-admina;
  intencja: filtrowanie głosowań widocznych dla usera — w mocku niedokończone).
- 200: **tablica** Voting z polami computed (`votesFor/Against`, `abstained`, `hasVoted`, `myVote`,
  `votedCount`, ...). FE zakłada, że odpowiedź jest tablicą (`data.forEach`, `.map`).

#### 9. `GET /api/votings/:id`
- Auth: Bearer. 200: pełny Voting + computed, w tym listy `eligibleUsers`, `votedUsers`,
  `notVotedUsers` (`{id,name,club}`), `totalEligible`, `votedCount`, `hasVoted`, `myVote`.
  Wyznaczanie uprawnionych na podstawie `recipientsType` (all/members/groups).
- 404: `{ message: "Nie znaleziono głosowania" }` (FE wyświetla `data.message`).
- FE (`VotingPage`) po pobraniu, jeśli `linkedItemType!=="none"`, dociąga #18b lub #27.

#### 10. `POST /api/votings`
- Auth: Bearer + JSON. Rola: admin/marszałek. Body = pełny Voting (patrz model; `startTime`
  = `datetime-local`, `endTime` jw. lub wyliczone). 200/201: utworzony obiekt z `id`
  (FE czyta `data.id`, potem opcjonalnie #15 dla załączników).

#### 11. `PUT /api/votings/:id`
- Auth: Bearer + JSON. Body jak w #10 (bez `managers` w EditVoting). 200: zaktualizowany obiekt
  (mock zwraca `{ success, message, voting }` **lub** sam obiekt — patrz rozbieżność w handlers).
  FE odczytuje tylko `response.ok` i ewentualnie `data.message`.

#### 12. `POST /api/votings/:id/vote`
- Auth: Bearer + JSON. Body: `{ "vote": "for"|"against"|"abstain" }`.
- 200: `{ message?, vote }` — FE czyta `data.vote` i ustawia `myVote`.
- Błędy: 400 `{ message: "Użytkownik już oddał głos" }`, 404 `{ message }`.
- ⚠️ FE wysyła `"abstain"`; magazyn/statystyki używają `"abstained"` (sekcja 6/8).

#### 13. `POST /api/votings/:id/activate`
- Auth: Bearer + JSON. Body: `{ startTime (ISO), endTime (ISO), duration (godz.), delay (min) }`.
- Efekt: `status → "active"`, ustawienie czasów. 200: `{ success, message, voting }`.

#### 14. `POST /api/votings/:id/archive`
- Auth: Bearer (+ `Content-Type: application/json`, ale **bez body**). Efekt: `status →
  "archived"`; dodatkowo aktualizacja statusu powiązanej uchwały/poprawki wg wyniku
  (`votesFor>votesAgainst ? accepted : rejected`) — patrz `updateLinkedItemStatus` w mocku.
- 200: `{ success: true, voting }` (FE sprawdza tylko `response.ok`, potem odświeża listę).

#### 15. `POST /api/votings/:id/attachments`
- Auth: Bearer. Body: `multipart/form-data`, pola `attachment_0`, `attachment_1`, ... (pliki).
- ⚠️ **Brak w API.md i w MSW** — endpoint wymyślony przez FE. FE nie czyta odpowiedzi (fire-and-forget).
  Wołany po utworzeniu/edycji głosowania, tylko jeśli dodano pliki.

#### 16. `DELETE /api/votings/:id` — (handler-only, nieużywany przez FE). Zaimplementować dla kompletności; 200 `{ success: true }`.

---

### RESOLUTIONS

#### 17. `GET /api/resolutions`
- Auth: `Resolutions.jsx` — brak; `CreateVoting`/`EditVoting` — Bearer.
- 200: **`{ resolutions: [ <Resolution> ] }`** (obiekt z kluczem `resolutions`).
  `Resolutions.jsx` czyta `data.resolutions`; Create/Edit tolerują wiele kształtów
  (`array`, `.data`, `.items`, `.resolutions`) — ale kanoniczny to `{ resolutions: [...] }`.
  (API.md dodaje jeszcze `session` na górnym poziomie — patrz sekcja 6.)

#### 18 / 18b. `GET /api/resolutions/:slug`
- Auth: brak (`ResolutionDetails`, `AddAmendment`); Bearer (`VotingPage` — ale **po ID**!).
- 200:
  ```json
  {
    "resolution": { ...Resolution, "chapters": [...] },
    "signedUsers": [ { "name", "club", "timestamp", "type" } ],
    "session": { "city", "date" },
    "currentUser": { "hasSigned": bool, "isAuthor": bool, "signatureType": "author"|"signature"|null, "isAutoSigned": bool }
  }
  ```
  `currentUser` obecne tylko gdy znany zalogowany user; `VotingPage` czyta z odpowiedzi jedynie
  `resolution`-podobne pola (`title, status, slug, description/preamble, author, createdAt`).
- ⚠️ **Ta sama ścieżka wołana raz po `slug`, raz po `id`** (#18b w `VotingPage`,
  `endpoint = /api/resolutions/${linkedItemId}`). Backend musi rozpoznawać oba (sekcja 6/8).
- 404: `{ message: "Nie znaleziono uchwały" }`.

#### 19. `POST /api/resolutions`
- Auth: **brak nagłówka** (XMLHttpRequest, `SubmitResolution`). Body: `multipart/form-data`:
  - `file`: plik `.docx`,
  - `data`: **string JSON** z: `{ ...editedData (title, chapters[], preamble?), fileName,
    author, authorId, party, sessionId }`.
    `editedData` pochodzi z lokalnego parsowania docx (`utils/docxParser`), zawiera
    `title` i `chapters:[{id,title,articles:[{id,number,content}]}]`.
- 200/201: utworzony obiekt Resolution (z wygenerowanym `slug`, `status:"pending"`, `signatures:1`,
  `createdAt`). Backend powinien wygenerować `slug` (mock: lowercase, spacje→`-`, usuń nie-`\w-`)
  i utworzyć auto-podpis autora (`type:"author"`).
- Błąd: `{ message }` z kodem !=2xx (FE pokazuje `error.message`).

#### 20. `GET /api/resolutions/session/:sessionId`
- Auth: brak. 200: `{ resolutions: [ <Resolution> ], sessionId, count }` (FE czyta `data.resolutions`).

#### 21. `POST /api/resolutions/:id/sign`
- Auth: brak (FE nie wysyła tokenu!). Body: brak. Tożsamość podpisującego = zalogowany user
  (backend musi znać usera z sesji/tokenu — konflikt z „brak auth", sekcja 8).
- 200: `{ success: true }`. Błąd 400: `{ message: "Już podpisałeś tę uchwałę" }`.
- FE po sukcesie odświeża #18.

#### 22. `DELETE /api/resolutions/:id/sign`
- Auth: brak. 200: `{ success: true, message: "Podpis został usunięty" }`.
- Błąd 403: `{ message: "Autor nie może usunąć podpisu" }`; 404 gdy brak podpisu.

---

### AMENDMENTS

#### 23 / 23b. `GET /api/resolutions/:slug/amendments`
- Auth: brak. `AmendmentsPage` — po `slug`; `FinalizeResolution` — **po `id`** (`resolutionId`).
- 200: `{ resolution: { title, slug }, session: { city, date }, amendments: [ <Amendment> ] }`.
  `FinalizeResolution` czyta `data.amendments`; `AmendmentsPage` czyta `resolution`, `amendments`, `session`.

#### 24. `POST /api/resolutions/:slug/amendments`
- Auth: brak. Body JSON (z `AddAmendment`):
  ```json
  {
    "resolutionId": int, "author": string, "authorId": int, "club": string,
    "content": string, "status": "pending",
    "changes": [ { "articleId": string|int, "type": "modify"|"add"|"delete", "before": string, "after": string } ],
    "withdrawnReason": null
  }
  ```
  (dla `add`: `articleId = "new_<timestamp>"`, `before=""`; dla `delete`: `after=""`).
- 200/201: `{ success: true, amendment: <Amendment> }`. Backend nadaje `id`, `createdAt`, `resolutionId`.
- 404 gdy uchwała nie istnieje.

#### 25. `GET /api/resolutions/:slug/amendments/:amendmentId`
- Auth: brak. 200: `{ resolution: { title, slug }, amendment: <Amendment>, session: { city, date } }`.
- 404: `{ message: "Nie znaleziono poprawki" }`.

#### 26. `GET /api/amendments`
- Auth: Bearer. 200: **tablica** `[ <Amendment> ]` (FE toleruje też `{amendments|data|items:[...]}`,
  ale kanon: goła tablica).

#### 27. `GET /api/amendments/:id`
- Auth: Bearer. 200: **`{ data: { ...Amendment, resolution: { id, title, slug } } }`**
  (opakowane w `data`; `VotingPage` czyta `linkedData.data`). 404: `{ message }`.

#### 28. `POST /api/amendments/:id/withdraw`
- Auth: brak. Body: `{ "reason": string }` (FE domyślnie „Brak podanego powodu").
  Autoryzacja: tylko autor poprawki (mock sprawdza `authorId===user.id` → 403 w innym wypadku;
  ale user brany z sesji, mimo braku tokenu — konflikt, sekcja 8).
- 200: `{ success: true, amendment: <Amendment (status:"withdrawn")> }`.
- Błędy: 404 (brak poprawki), 400 (już wycofana), 403 (nie autor).

---

### PARLIAMENTARIANS

#### 29. `GET /api/parliamentarians`
- Auth: Bearer. 200: `{ parliamentarians: [ <P z clubId != null> ], unaffiliated: [ <P z clubId=null> ] }`.
  (`LiveVoting` toleruje też gołą tablicę, ale kanon jak wyżej.)

#### 30. `POST /api/parliamentarians`
- Auth: Bearer + JSON. Body: `{ firstName, lastName, clubId (int|null), functions: string[], commissions: string[] }`.
- 200/201: utworzony `<Parliamentarian>` z rozwiniętym `clubName`/`clubColor` (z klubu).
- ⚠️ FE używa tego endpointu **także do edycji** (funkcja `saveParliamentarian` zawsze POST).
  `PUT /api/parliamentarians/:id` (#31) istnieje w mocku/API.md, ale FE go **nie woła** — edycja
  parlamentarzysty jest w praktyce zepsuta (tworzy duplikat). Patrz sekcja 8.

#### 31. `PUT /api/parliamentarians/:id` — (handler-only). Zaimplementować; body jak #30; 200: zaktualizowany obiekt.

#### 32. `DELETE /api/parliamentarians/:id`
- Auth: Bearer. Efekt: usuń + wypnij z klubu. 200: `{ success: true }`.

---

### CLUBS

#### 33. `GET /api/clubs`
- Auth: Bearer. 200: **tablica** `[ <Club> ]`. FE czyta `id, name, type, color`; oblicza liczność
  z listy parlamentarzystów (nie z `members`).
- ⚠️ Dane mocka klubów **nie mają** pola `members`, a handlery/API.md je zakładają (sekcja 6).
  Backend: zwracać `members: []` lub wypełnione — FE i tak nie polega na `members` tutaj.

#### 34. `POST /api/clubs`
- Auth: Bearer + JSON. Body: `{ name, type: "klub"|"koło"|"komitet", color }`. 200/201:
  `<Club>` z `id` i `members: []`.

#### 35. `PUT /api/clubs/:id`
- Auth: Bearer + JSON. Body jak #34. 200: zaktualizowany `<Club>`.

#### 36. `DELETE /api/clubs/:id`
- Auth: Bearer. Efekt: usuń klub, wypnij członków (`clubId→null`). 200: `{ success: true }`.

#### 37 / 38. `POST/DELETE /api/clubs/:id/members[/:memberId]` — (handler-only, nieużywane; opcjonalne). Zwracają `{ club, parliamentarians, unaffiliated }`.

---

### SPEAKERS / GROUPS / MEMBERS / USERS

#### 39. `GET /api/speakers` — Auth: Bearer. 200: tablica `[{ name, club, role }]`.
#### 40. `POST /api/speakers` — Auth: Bearer + JSON. Body: `{ name, club, role }`. 200/201: `{ id, name, club, role }` (FE dopisuje do listy).
#### 41. `GET /api/groups` — Auth: Bearer. 200: tablica `[{ id, name }]` (opcjonalnie `memberCount`).
#### 42. `GET /api/members` — Auth: Bearer. 200: tablica `[{ id, name, group }]`.
#### 43. `GET /api/users` — Auth: Bearer. 200: tablica `[ <User> ]`. Używane do wyboru „managerów"
  głosowania (FE czyta `id, name, role, group`). **Nie zwracać `password`.**

---

## 5. Realtime (Socket.IO)

> Cała warstwa realtime w `SocketProvider.jsx` jest **zakomentowana** — `socket === null`, więc
> obecnie żaden event nie leci. Poniższe wynika z kodu nasłuchującego w komponentach oraz z
> zakomentowanej konfiguracji (traktować jako **docelowy kontrakt** do włączenia).

- **Transport/URL (z zakomentowanego kodu):**
  ```js
  const SOCKET_URL = "http://localhost:4000";
  io(SOCKET_URL, { transports: ["websocket"], autoConnect: true });
  ```
  Nasłuch stanu połączenia: `connect`, `disconnect`, `connect_error`. Osobny port (4000) niż API.

- **Events (kierunek: S→C = serwer do klienta, C→S = klient do serwera):**

| Event | Kierunek | Payload | Miejsce / moment |
|---|---|---|---|
| `voteUpdate:<votingId>` | S→C | `{ votedCount, votesFor, votesAgainst, abstained, votedUsers[], notVotedUsers[] }` | `LiveVoting.jsx` — po każdym oddanym głosie w danym głosowaniu (nazwa eventu zawiera id głosowania) |
| `zoContentUpdated` | S→C **oraz** C→S | `zoContent` (string) | `SessionDetails.jsx` — zmiana treści trybu „ZO"; admin emituje po zapisie, wszyscy odbierają |
| `scheduleUpdated` | S→C | `newSchedule` (tablica pozycji harmonogramu) | `SessionDetails.jsx` — aktualizacja harmonogramu posiedzenia |
| `speakerUpdated` | S→C | `newSpeaker` (`{ name, club, role, time }`) | `SessionDetails.jsx` — zmiana aktualnego mówcy |

- **Fallback polling:** `LiveVoting` gdy `!isConnected` odpytuje `GET /api/votings/:id` co 3 s
  (odczytuje te same pola co z eventu). Backend REST musi więc zwracać spójne dane live.

- **Rozbieżność z API.md:** dokumentacja opisuje `ws://server/api/votings/:id/live` z eventem
  `VOTE_UPDATE` (`{ type, data:{ for, against, abstain, voted, notVoted, total } }`). Kod używa
  **Socket.IO** (nie gołego WS), innej nazwy eventu (`voteUpdate:<id>`) i innych nazw pól
  (`votesFor` vs `for`). **Kod jest źródłem prawdy.**

---

## 6. Rozbieżności

### 6.1. Kod vs kod (wewnątrz frontendu) — do pogodzenia po stronie backendu
1. **Bieżąca sesja pod dwiema ścieżkami:** `GET /api/session/current` (SessionDetails) vs
   `GET /api/sessions/current` (Dashboard). Do tego różne odczytywane pola (`date`/`status` vs
   `start`/`startTime`/`end`/`endTime`). **Rekomendacja:** backend obsługuje **oba** aliasy i
   zwraca obiekt zawierający **wszystkie** pola (`title, status, date, start, startTime, end,
   endTime, currentSpeaker, currentPoint, schedule, zoContent`).
2. **Uchwała po `slug` vs po `id`:** `GET /api/resolutions/:slug` wołane w `VotingPage` z
   `linkedItemId` (liczbą). **Rekomendacja:** parametr traktować polimorficznie — jeśli czysto
   numeryczny, szukać po `id`; w przeciwnym razie po `slug`.
3. **Poprawki uchwały po `slug` vs po `id`:** `GET /api/resolutions/:x/amendments` — `AmendmentsPage`
   podaje `slug`, `FinalizeResolution` podaje `resolutionId`. Jak wyżej — obsłużyć oba.
4. **Dwa endpointy „kto jestem":** `GET /api/auth/me` (zwraca gołego usera) vs
   `GET /api/current-user` (zwraca `{ user }`). **Rekomendacja:** zaimplementować oba; `/current-user`
   opakowuje w `user`.
5. **Enum głosu:** wysyłka `"abstain"` (`VotingPage`) vs magazyn/statystyki `"abstained"`
   (`votes.js`, liczenie). **Rekomendacja:** backend akceptuje `"abstain"` na wejściu i normalizuje
   do jednej wartości; statystykę „wstrzymań" liczyć spójnie. (Albo poprawić FE — sekcja 8.)
6. **`recipientsType`:** FE używa `all`/`groups`/`members`, ale UI CreateVoting/EditVoting bywa
   ustawia `"individual"` (mapowane lokalnie na „members"). Backend powinien traktować
   `individual` == `members`.
7. **Edycja parlamentarzysty przez POST:** FE nigdy nie woła `PUT /api/parliamentarians/:id` —
   „edycja" leci jako `POST /api/parliamentarians` (tworzy nowy rekord). Funkcjonalnie zepsute.
8. **Niespójny auth na tym samym zasobie:** `/api/resolutions` i `/api/auth/me` bywają wołane raz
   z tokenem, raz bez. **Rekomendacja:** odczyty z auth *opcjonalnym*.
9. **Malformowany nagłówek `Authorization`** (sekcja 1.4) — bearer to JSON `{token,expiresAt}`, a nie sam JWT.

### 6.2. Kod vs `API.md`
1. **Realtime:** API.md = goły WebSocket `ws://.../api/votings/:id/live`, event `VOTE_UPDATE`,
   pola `for/against/abstain/voted/notVoted/total`. Kod = Socket.IO na `:4000`, event
   `voteUpdate:<id>`, pola `votesFor/votesAgainst/abstained/votedCount`. → **Kod wygrywa.**
2. **`POST /api/resolutions`:** API.md pokazuje body **JSON**. Kod wysyła **`multipart/form-data`**
   (`file` + `data` jako JSON string). → **Kod wygrywa.**
3. **`GET /api/votings/:id`:** API.md ma wariant `canSeeLiveResults`/`liveResults`. Kod tego nie
   używa — zamiast tego oczekuje `eligibleUsers/votedUsers/notVotedUsers/votedCount/totalEligible`
   oraz `votesFor/votesAgainst/abstained`. → **Kod wygrywa.**
4. **`GET /api/resolutions`:** API.md ma `{ session, resolutions }`; kod/mock zwraca `{ resolutions }`.
   Bezpiecznie zwracać oba klucze.
5. **`POST /api/votings/:id/attachments`:** brak w API.md i w MSW; istnieje tylko w kodzie FE.
6. **`GET /api/session/current` bez sesji:** API.md = `{ message }` / 401; mock zawsze zwraca obiekt.
7. **`Club.members`:** API.md/handlery zakładają `members[]`, dane mocka klubów go nie mają.
8. **Ścieżka `/api/sessions/current`** (Dashboard) i `/api/current-user` (AmendmentsPage) — brak w API.md.

---

## 7. Wymagania dev-setup

### 7.1. Stan obecny (dlaczego FE działa bez backendu)
- `src/main.jsx` startuje **MSW** gdy `import.meta.env.DEV` (jest tam też zakomentowane
  `// if (false)`), więc w dev **wszystkie `/api/*` są przechwytywane przez mock** i nie docierają
  do żadnego serwera.
- `vite.config.js` **nie ma `server.proxy`**. `base` = `/mparlament/` tylko w produkcji.
- Frontend używa `HashRouter` — routing po `#`, więc backend nie musi obsługiwać deep-linków SPA.

### 7.2. Co zmienić, aby FE (dev) gadał z realnym backendem
1. **Wyłączyć MSW** w dev: w `src/main.jsx` zmienić warunek `enableMocking` tak, by nie startował
   worker (np. użyć gałęzi `if (false)`), albo sterować flagą env.
2. **Dodać proxy w Vite** (żeby uniknąć CORS i zachować ścieżki względne `/api`):
   ```js
   // vite.config.js
   server: {
     proxy: {
       "/api":       { target: "http://localhost:4000", changeOrigin: true },
       "/uploads":   { target: "http://localhost:4000", changeOrigin: true }, // pliki uchwał
       "/socket.io": { target: "http://localhost:4000", ws: true },           // jeśli Socket.IO za proxy
     }
   }
   ```
   (Port backendu do ustalenia — sekcja 8. FE dla Socket.IO ma na sztywno `http://localhost:4000`.)
3. **Statyczne pliki uchwał:** FE linkuje do `/uploads/resolutions/<fileName>` (fallback, gdy brak
   `resolution.filePath`). Backend powinien serwować wgrane pliki pod tą ścieżką lub zwracać
   pełny `filePath` w modelu Resolution.
4. **CORS / same-origin:**
   - Z proxy Vite → żądania są same-origin, CORS niepotrzebny.
   - Bez proxy (FE bije wprost na `:4000`) → backend musi zwracać `Access-Control-Allow-Origin`
     dla originu dev (`http://localhost:5173`) oraz obsłużyć preflight (nagłówki `Authorization`,
     `Content-Type`).
   - **Socket.IO** na `:4000` — skonfigurować CORS serwera Socket.IO dla originu frontendu.
5. **Upload:** backend musi przyjmować `multipart/form-data` na #15 i #19 (parser typu `multer`).

### 7.3. Produkcja
- FE budowany z `base: /mparlament/` (GitHub Pages: `npm run deploy`). API musi być dostępne pod
  tym samym originem/przez proxy pod `/api`, bo FE nie zna absolutnego URL backendu.

---

## 8. Otwarte decyzje wymagające potwierdzenia

1. **Nagłówek `Authorization`** — FE wysyła `Bearer <cały JSON {token,expiresAt}>`, nie sam JWT.
   Czy: (a) poprawić frontend, by wysyłał `parsed.token` (rekomendacja), czy (b) backend ma
   parsować JSON z bearera i wyciągać `token`? Wpływa na całą warstwę auth.
2. **Endpointy publiczne wołane bez tokenu, a wymagające tożsamości** (#21/#22 sign, #28 withdraw,
   #2b/#3 „me") — jak backend ma ustalić usera bez `Authorization`? Opcje: (a) poprawić FE, by
   dosyłał token (rekomendacja), (b) sesja cookie, (c) przyjmować `authorId`/`userId` z body.
   Bez decyzji nie da się bezpiecznie autoryzować podpisów i wycofań.
3. **Ujednolicenie ścieżek** (sesja `session/current` vs `sessions/current`; „me" vs
   „current-user"; uchwała/poprawki po `slug` vs `id`). Potwierdzić: backend robi aliasy i
   polimorficzne parametry (rekomendacja, zero zmian w FE) — czy prostujemy FE?
4. **Enum „wstrzymanie się":** kanoniczna wartość — `"abstain"` czy `"abstained"`? Rekomendacja:
   przyjmować `"abstain"` z FE i normalizować (a docelowo poprawić `votes`/liczenie do jednej nazwy).
5. **Edycja parlamentarzysty** — FE nie woła `PUT`. Zaimplementować `PUT` **i** poprawić FE
   (rekomendacja), czy tolerować POST jako upsert po `id`?
6. **Załączniki głosowań (#15)** — potwierdzić kontrakt (nazwy pól `attachment_<i>`, limit 10 MB
   walidowany w FE, brak w API.md). Gdzie przechowywać i jak zwracać w `Voting.attachments`?
7. **Model uprawnień per endpoint** — z kodu wynikają role/permisje (poniżej). Potwierdzić, które
   backend ma egzekwować (FE i tak ukrywa akcje, ale nie zabezpiecza API):
   - `admin` **lub** `permissions:["MANAGE_VOTINGS"]` → tworzenie/edycja/aktywacja/archiwizacja
     głosowań, podgląd „live" list uprawnionych; dodatkowo `managers[]` danego głosowania mają
     prawa edycji/aktywacji/live tego głosowania.
   - `admin`/`marshal` → zarządzanie sesją (`PUT /api/session/current`), dodawanie mówców,
     finalizacja uchwał (link „Finalizuj" widoczny dla admina / `MANAGE_RESOLUTIONS`).
   - `admin` **lub** `permissions:["MANAGE_PARLIAMENTARIANS"]` → CRUD parlamentarzystów i klubów.
   - `member` → głosowanie, podpisywanie/wycofywanie własnych podpisów, dodawanie poprawek,
     wycofywanie **własnych** poprawek (autor).
8. **Port i host backendu / Socket.IO** — FE ma na sztywno `http://localhost:4000` dla socketu.
   Potwierdzić port HTTP API (proponowany też `4000`) i czy Socket.IO działa na tym samym porcie
   czy osobnym.
9. **Realtime** — czy wdrażamy Socket.IO wg sekcji 5 (odkomentować `SocketProvider`), czy na start
   zostajemy przy pollingu REST (`GET /api/votings/:id` co 3 s), a socket dodamy później?
