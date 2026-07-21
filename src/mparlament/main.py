"""ASGI application factory.

Slice routers are included under ``/api`` as they are built (each router carries its own
sub-path). Static uploads are served from ``/uploads`` so the FE fallback
``/uploads/resolutions/<fileName>`` resolves (CONVENTIONS C14).
"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from mparlament.shared.api import register_exception_handlers
from mparlament.shared.config import Settings, get_settings

# Slice routers are appended here as slices are implemented.
SLICE_ROUTERS: list[APIRouter] = []

health_router = APIRouter()


@health_router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    app = FastAPI(title="mparlament-backend")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # Map DomainError -> {"message": ...} with the right status (CONVENTIONS C11).
    register_exception_handlers(app)

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

    return app


app = create_app()
