# Deployment

The whole app ships as **one Docker image**: the API, Socket.IO and the built React SPA are
served from a single origin on a single port. That matters because the frontend calls the API
with relative paths (`fetch("/api/...")`) and opens its Socket.IO connection same-origin — so a
one-origin deployment needs no frontend code changes and involves no CORS.

```
                 ┌──────────────────────── container ────────────────────────┐
  browser ──────▶│  uvicorn → socketio.ASGIApp                               │
                 │      ├── /socket.io/…  Socket.IO (realtime, spec §5)      │
                 │      └── FastAPI                                          │
                 │            ├── /api/…      REST                           │
                 │            ├── /uploads/…  uploaded files  (/app/uploads) │
                 │            └── /…          built SPA        (/app/static) │
                 └───────────────────────────────────────────────────────────┘
```

The SPA mount is added last, so `/api` and `/uploads` keep precedence. It only exists when
`MPARLAMENT_STATIC_DIR` points at a real directory — local dev runs are unaffected.

## What happens on container start

`docker/entrypoint.sh`:

1. Copies `RENDER_EXTERNAL_URL` into `MPARLAMENT_PUBLIC_ORIGIN` when the latter is unset.
2. Runs `alembic upgrade head` **if** `migrations/versions/` holds any revision (it currently
   holds none).
3. Runs `python scripts/seed.py` unless `MPARLAMENT_SEED_ON_START=false`. This is what creates
   the schema (`Base.metadata.create_all`) and upserts the demo data, including the `TEST123`
   account — with no Alembic revisions in the repo, skipping it leaves you without tables.
4. Execs uvicorn on `$PORT` with **one worker**.

## Environment variables

| Variable | Default | Notes |
| --- | --- | --- |
| `MPARLAMENT_JWT_SECRET` | `dev-insecure-change-me` | Set a real secret in any hosted environment. |
| `MPARLAMENT_PUBLIC_ORIGIN` | — | Public origin, e.g. `https://mparlament.onrender.com`. **Required for realtime**, see below. Auto-filled on Render. |
| `MPARLAMENT_DATABASE_URL` | `sqlite+aiosqlite:////app/data/mparlament.db` (in the image) | |
| `MPARLAMENT_STATIC_DIR` | `/app/static` (in the image) | Built SPA; unset it to serve the API only. |
| `MPARLAMENT_UPLOAD_DIR` | `/app/uploads` (in the image) | |
| `MPARLAMENT_SEED_ON_START` | `true` | See step 3 above before turning this off. |
| `MPARLAMENT_CORS_ORIGINS` | `["http://localhost:5173"]` | JSON list. Only needed if a *different* origin must reach the API. |
| `PORT` | `4000` | Injected by Render. |

### Why `MPARLAMENT_PUBLIC_ORIGIN` is required

Engine.IO checks the `Origin` header of every Socket.IO handshake against a fixed list and
rejects anything outside it with `400 Not an accepted origin` — **including the app's own
origin**. `Settings.allowed_origins` therefore appends `public_origin` to `cors_origins`, and
both the CORS middleware and the Socket.IO server use that list. Without it, REST keeps working
and realtime silently fails.

## Deploying on Render

The frontend is fetched from its own repository at image build time (`FRONTEND_SLUG` /
`FRONTEND_REF` build args), so **only this repository has to be connected to Render**.

1. Push this repository to GitHub.
2. Make sure the frontend ref you are going to build actually contains the same-origin setup
   (relative `/api` fetches, `SocketProvider` defaulting to same-origin, MSW gated behind
   `VITE_USE_MOCKS`). Pin `FRONTEND_REF` to that commit SHA.
3. In Render: **New → Blueprint**, select the repo, confirm `render.yaml`.
   (Manual alternative: New → Web Service → Docker runtime, health check path `/api/health`.)
4. Wait for the build, open the service URL. The SPA loads at `/`, the API answers under
   `/api`, and `TEST123` is available from the seed.

### Free-plan caveats

- **The filesystem is ephemeral.** `/app/data` (SQLite) and `/app/uploads` are wiped on every
  deploy and restart; the seed rebuilds the demo data, uploaded files are gone. For durable
  data, either attach a persistent disk mounted at `/app/data` (paid plan) or switch
  `MPARLAMENT_DATABASE_URL` to Postgres (`postgresql+asyncpg://…`, which needs `asyncpg` added
  to the dependencies and real Alembic revisions).
- **The service sleeps after ~15 minutes of inactivity**; the next request takes ~50 s.
- **Keep it at one instance.** Socket.IO state lives in-process; horizontal scaling needs a
  Redis manager first.

## Running the image locally

```bash
docker compose up --build          # → http://localhost:4000
```

Compose keeps the DB and uploads in named volumes, so local data survives restarts. To build a
different frontend ref:

```bash
FRONTEND_REF=<branch-tag-or-sha> docker compose up --build
```

## Troubleshooting

- **Realtime dead, `400` on `/socket.io/`** — `MPARLAMENT_PUBLIC_ORIGIN` is missing or does not
  match the browser's origin exactly (scheme + host + port, no trailing slash).
- **Frontend changes not showing up** — a cached build layer is holding an old clone. Pin
  `FRONTEND_REF` to a SHA, or use Render's *Clear build cache & deploy*.
- **`entrypoint.sh: not found`** — the script got CRLF line endings. `.gitattributes` forces LF;
  re-check out the file if it was committed before that.
- **Blank page with 404s on `/mparlament/assets/…`** — the image must build the SPA with
  `npm run build -- --base=/` (the repo default targets gh-pages under `/mparlament/`).
  Building by hand in Git Bash needs `MSYS_NO_PATHCONV=1`, or `/` gets rewritten to a Windows
  path.
