#!/bin/sh
# Container entrypoint: prepare the schema/data, then hand over to uvicorn.
set -eu

: "${PORT:=4000}"

# Socket.IO (engine.io) validates the Origin header against a fixed list and rejects anything
# outside it -- including the app's own origin. Render exposes the public URL as
# RENDER_EXTERNAL_URL; anywhere else, set MPARLAMENT_PUBLIC_ORIGIN yourself.
if [ -z "${MPARLAMENT_PUBLIC_ORIGIN:-}" ] && [ -n "${RENDER_EXTERNAL_URL:-}" ]; then
    MPARLAMENT_PUBLIC_ORIGIN="${RENDER_EXTERNAL_URL}"
    export MPARLAMENT_PUBLIC_ORIGIN
fi
echo "==> public origin: ${MPARLAMENT_PUBLIC_ORIGIN:-<unset>}"

# Only run Alembic once revisions exist (the repo has none yet -- the schema is created by the
# seed's create_all).
if ls migrations/versions/*.py >/dev/null 2>&1; then
    echo "==> alembic upgrade head"
    alembic upgrade head
fi

# Idempotent: creates any missing tables and upserts the demo data by natural key.
if [ "${MPARLAMENT_SEED_ON_START:-true}" = "true" ]; then
    echo "==> seeding demo data"
    python scripts/seed.py
fi

echo "==> uvicorn on :${PORT}"
# Exactly one worker: Socket.IO keeps client state in-process (no Redis adapter), so a second
# worker would silently drop events for clients attached to the other one.
exec uvicorn mparlament.main:create_asgi_app     --factory     --host 0.0.0.0     --port "${PORT}"     --workers 1     --proxy-headers     --forwarded-allow-ips="*"
