"""Async SQLAlchemy engine, session factory, declarative Base and FastAPI dependency.

SQLite foreign-key enforcement is turned on per-connection (SQLite defaults to OFF).
Slice ORM models are registered in :mod:`mparlament.shared.models_registry` so that
Alembic autogenerate and ``Base.metadata.create_all`` see every table.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from mparlament.shared.config import get_settings


class Base(DeclarativeBase):
    """Declarative base shared by every slice's ORM models."""


def enable_sqlite_fk(async_engine: AsyncEngine) -> None:
    """Enforce foreign keys on SQLite (disabled by default) for the given engine.

    Reusable so the test harness can apply it to its own engine.
    """

    @event.listens_for(async_engine.sync_engine, "connect")
    def _set_pragma(dbapi_connection: object, _record: object) -> None:
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


settings = get_settings()

engine = create_async_engine(settings.database_url, future=True)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)

if engine.dialect.name == "sqlite":
    enable_sqlite_fk(engine)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yield a session, commit on success, roll back on error."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
