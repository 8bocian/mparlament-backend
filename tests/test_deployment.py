"""Deployment wiring: public origin (CORS/Socket.IO) + built SPA served from the app.

The production image serves the React build and the API from one origin (see DEPLOYMENT.md),
so the app must (a) accept its own public origin — engine.io rejects any origin outside the
configured list, even a same-origin one — and (b) mount the built SPA at ``/`` without
shadowing ``/api`` or ``/uploads``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from mparlament.main import create_app
from mparlament.shared.config import Settings


def test_allowed_origins_defaults_to_cors_origins() -> None:
    settings = Settings(cors_origins=["http://localhost:5173"], public_origin=None)

    assert settings.allowed_origins == ["http://localhost:5173"]


def test_allowed_origins_includes_public_origin() -> None:
    settings = Settings(
        cors_origins=["http://localhost:5173"],
        public_origin="https://mparlament.onrender.com",
    )

    assert settings.allowed_origins == [
        "http://localhost:5173",
        "https://mparlament.onrender.com",
    ]


def test_allowed_origins_strips_trailing_slash_and_dedupes() -> None:
    settings = Settings(
        cors_origins=["https://mparlament.onrender.com"],
        public_origin="https://mparlament.onrender.com/",
    )

    assert settings.allowed_origins == ["https://mparlament.onrender.com"]


@pytest.fixture
def spa_dir(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>mparlament</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('spa')", encoding="utf-8")
    return dist


async def _client(settings: Settings) -> AsyncClient:
    app = create_app(settings)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.anyio
async def test_spa_is_served_at_root_when_static_dir_configured(
    spa_dir: Path, tmp_path: Path
) -> None:
    settings = Settings(static_dir=spa_dir, upload_dir=tmp_path / "uploads")

    async with await _client(settings) as ac:
        root = await ac.get("/")
        asset = await ac.get("/assets/app.js")

    assert root.status_code == 200
    assert "<title>mparlament</title>" in root.text
    assert asset.status_code == 200


@pytest.mark.anyio
async def test_spa_mount_does_not_shadow_the_api(spa_dir: Path, tmp_path: Path) -> None:
    settings = Settings(static_dir=spa_dir, upload_dir=tmp_path / "uploads")

    async with await _client(settings) as ac:
        response = await ac.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_app_boots_without_a_static_dir(tmp_path: Path) -> None:
    settings = Settings(static_dir=None, upload_dir=tmp_path / "uploads")

    async with await _client(settings) as ac:
        root = await ac.get("/")
        health = await ac.get("/api/health")

    assert root.status_code == 404
    assert health.status_code == 200


@pytest.mark.anyio
async def test_missing_static_dir_is_ignored(tmp_path: Path) -> None:
    """A stale MPARLAMENT_STATIC_DIR must not crash the app (dev runs have no build)."""
    settings = Settings(static_dir=tmp_path / "nope", upload_dir=tmp_path / "uploads")

    async with await _client(settings) as ac:
        health = await ac.get("/api/health")

    assert health.status_code == 200
