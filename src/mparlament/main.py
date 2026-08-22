"""ASGI application factory.

Slice routers are included under ``/api`` as they are built (each router carries its own
sub-path). Static uploads are served from ``/uploads`` so the FE fallback
``/uploads/resolutions/<fileName>`` resolves (CONVENTIONS C14).

Realtime (doc 10 / spec §5) is layered on top without touching :func:`create_app`: the pure
FastAPI app stays the target for the httpx test harness, while :func:`create_asgi_app` wraps it in a
Socket.IO ``ASGIApp`` and registers the concrete :class:`SocketIOEventPublisher` so the REST write
use cases (which already hold the deferred publisher) light up their emits. Run the combined app
with ``uvicorn mparlament.main:create_asgi_app --factory --port 4000``.
"""

from __future__ import annotations

from collections.abc import Callable

import socketio
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from mparlament.shared.api import register_exception_handlers
from mparlament.shared.auth import set_user_reader
from mparlament.shared.config import Settings, get_settings
from mparlament.shared.db import async_session_factory
from mparlament.shared.realtime import (
    SocketIOEventPublisher,
    deferred_event_publisher,
    set_event_publisher,
)
from mparlament.slices.amendments.api.router import router as amendments_router
from mparlament.slices.auth_identity.api.router import router as auth_identity_router
from mparlament.slices.auth_identity.infrastructure.reader import SqlAlchemyUserReader
from mparlament.slices.groups_members.api.router import router as groups_members_router
from mparlament.slices.parliamentarians_clubs.api.router import (
    router as parliamentarians_clubs_router,
)
from mparlament.slices.resolutions.api.router import router as resolutions_router
from mparlament.slices.sessions.api.router import router as sessions_router
from mparlament.slices.sessions.application.use_cases import UpdateCurrentSessionUseCase
from mparlament.slices.sessions.infrastructure.repository import (
    SqlAlchemyCurrentSessionRepository,
)
from mparlament.slices.users.api.router import router as users_router
from mparlament.slices.votings.api.router import router as votings_router

# Slice routers are appended here as slices are implemented.
SLICE_ROUTERS: list[APIRouter] = [
    auth_identity_router,
    users_router,
    sessions_router,
    votings_router,
    resolutions_router,
    amendments_router,
    parliamentarians_clubs_router,
    groups_members_router,
]

health_router = APIRouter()


@health_router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    app = FastAPI(title="mparlament-backend")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # Map DomainError -> {"message": ...} with the right status (CONVENTIONS C11).
    register_exception_handlers(app)

    # Supply the shared auth deps with a concrete identity reader (doc 01 UserReader port).
    set_user_reader(SqlAlchemyUserReader())

    app.include_router(health_router, prefix="/api")
    for router in SLICE_ROUTERS:
        app.include_router(router, prefix="/api")

    resolutions_dir = settings.upload_dir / "resolutions"
    resolutions_dir.mkdir(parents=True, exist_ok=True)
    app.mount(
        "/uploads",
        StaticFiles(directory=str(settings.upload_dir)),
        name="uploads",
    )

    # Built React SPA (single-container deployment, see DEPLOYMENT.md). Mounted last so
    # /api and /uploads keep precedence; ``html=True`` serves index.html at "/". The FE uses
    # HashRouter, so no history fallback is needed. Absent in dev -> nothing is mounted.
    if settings.static_dir is not None and settings.static_dir.is_dir():
        app.mount(
            "/",
            StaticFiles(directory=str(settings.static_dir), html=True),
            name="spa",
        )

    return app


# --- Realtime (doc 10 / spec §5) -------------------------------------------


async def handle_zo_content_updated(
    session_factory: Callable[[], object],
    data: object,
    publisher=deferred_event_publisher,  # noqa: ANN001 - EventPublisher
) -> None:
    """Inbound ``zoContentUpdated`` (C→S): persist the ZO text, then rebroadcast to all clients.

    The rebroadcast rides on :class:`UpdateCurrentSessionUseCase`'s own emit — persisting through
    the same use case that the REST PUT uses keeps one code path (doc 10 hook point).
    """
    use_case = UpdateCurrentSessionUseCase(
        SqlAlchemyCurrentSessionRepository(), publisher
    )
    async with session_factory() as session:  # type: ignore[operator]
        try:
            await use_case.execute(session, {"zoContent": data})
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def build_socket_server(
    settings: Settings,
    session_factory: Callable[[], object] | None = None,
) -> socketio.AsyncServer:
    """Build the Socket.IO ``AsyncServer`` with connection + inbound-event handlers (spec §5)."""
    factory = session_factory or async_session_factory
    sio = socketio.AsyncServer(
        async_mode="asgi", cors_allowed_origins=settings.allowed_origins
    )

    @sio.event
    async def connect(sid, environ, auth=None):  # noqa: ANN001, ARG001
        return None

    @sio.event
    async def disconnect(sid):  # noqa: ANN001, ARG001
        return None

    @sio.on("zoContentUpdated")
    async def zo_content_updated(sid, data):  # noqa: ANN001, ARG001
        await handle_zo_content_updated(factory, data)

    return sio


def create_asgi_app(settings: Settings | None = None) -> socketio.ASGIApp:
    """Combined ASGI app: Socket.IO (spec §5) mounted alongside the FastAPI API on one port (C14).

    Registers a concrete :class:`SocketIOEventPublisher` as the process publisher so the REST write
    use cases' deferred emits reach connected clients.
    """
    settings = settings or get_settings()
    fastapi_app = create_app(settings)
    sio = build_socket_server(settings)
    set_event_publisher(SocketIOEventPublisher(sio))
    return socketio.ASGIApp(sio, other_asgi_app=fastapi_app)


app = create_app()
