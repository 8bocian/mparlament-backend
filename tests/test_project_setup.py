"""Slice 00 — project setup TDD checklist (red-first)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from sqlalchemy import text

from mparlament.main import create_app
from mparlament.shared.config import get_settings

pytestmark = pytest.mark.anyio


async def test_app_boots(client) -> None:
    assert isinstance(create_app(), FastAPI)
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_cors_preflight(client) -> None:
    resp = await client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


async def test_static_uploads_mounted(client, tmp_path, monkeypatch) -> None:
    settings = get_settings()
    resolutions = settings.upload_dir / "resolutions"
    resolutions.mkdir(parents=True, exist_ok=True)
    target = resolutions / "x.txt"
    target.write_text("hello uploads", encoding="utf-8")
    try:
        resp = await client.get("/uploads/resolutions/x.txt")
        assert resp.status_code == 200
        assert resp.text == "hello uploads"
    finally:
        target.unlink(missing_ok=True)


async def test_db_session_fixture(async_session) -> None:
    result = await async_session.execute(text("SELECT 1"))
    assert result.scalar_one() == 1


def test_settings_defaults() -> None:
    settings = get_settings()
    assert settings.port == 4000
    assert settings.database_url.startswith("sqlite+aiosqlite")
