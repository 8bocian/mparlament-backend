"""Pytest harness (TDD backbone).

Async tests run on the anyio pytest plugin — mark them ``@pytest.mark.anyio`` (or rely on
the ``anyio_backend`` fixture). Each test gets an isolated in-memory SQLite database created
via ``Base.metadata.create_all`` (no Alembic needed in tests); a shared connection
(``StaticPool``) lets the ``async_session`` fixture and the ASGI app see the same data.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import AsyncIterator

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from mparlament.main import create_app
from mparlament.shared.config import get_settings
from mparlament.shared.db import Base, enable_sqlite_fk, get_session

# Ensure every slice's ORM models are registered on Base.metadata.
import mparlament.shared.models_registry  # noqa: F401


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    enable_sqlite_fk(engine)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest.fixture
async def async_session(db_engine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
async def client(db_engine) -> AsyncIterator[AsyncClient]:
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def _override_get_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app = create_app()
    app.dependency_overrides[get_session] = _override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


def make_token(**claims: object) -> str:
    """Mint a valid JWT for tests. Defaults ``sub`` and an ``exp`` 10h out."""
    settings = get_settings()
    payload: dict[str, object] = {"sub": "user-1"}
    payload.update(claims)
    if "exp" not in payload:
        payload["exp"] = dt.datetime.now(tz=dt.timezone.utc) + dt.timedelta(
            hours=settings.jwt_ttl_hours
        )
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@pytest.fixture
def auth_headers():
    """Return a raw-JWT Bearer header dict (CONVENTIONS C1, plain form)."""

    def _make(**claims: object) -> dict[str, str]:
        return {"Authorization": f"Bearer {make_token(**claims)}"}

    return _make


@pytest.fixture
def auth_headers_json():
    """Return a JSON-wrapped Bearer header (CONVENTIONS C1, localStorage-blob form).

    The FE may send ``Bearer {"token": "<jwt>", "expiresAt": <ms>}``; the tolerant parser
    must accept it. This variant exercises that path.
    """

    def _make(**claims: object) -> dict[str, str]:
        import json

        token = make_token(**claims)
        expires_ms = int(
            (
                dt.datetime.now(tz=dt.timezone.utc) + dt.timedelta(hours=10)
            ).timestamp()
            * 1000
        )
        blob = json.dumps({"token": token, "expiresAt": expires_ms})
        return {"Authorization": f"Bearer {blob}"}

    return _make
