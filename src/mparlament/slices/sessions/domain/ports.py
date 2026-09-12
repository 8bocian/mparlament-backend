"""Domain ports for the sessions slice (dependency inversion).

The application layer depends on these Protocols; SQLAlchemy adapters live in ``infrastructure``.
v1 keeps a single live-session row (C6 / KISS), so ``CurrentSessionRepository`` is get/save on a
singleton; ``SessionRepository`` lists the sitting rows (#7); ``SpeakerRepository`` lists/adds the
speaker registry (#39/#40).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.slices.sessions.domain.entities import (
    CurrentSession,
    Session,
    Speaker,
)


@runtime_checkable
class CurrentSessionRepository(Protocol):
    """Persistence port for the singleton live session."""

    async def get(self, session: AsyncSession) -> CurrentSession | None: ...

    async def save(
        self, session: AsyncSession, current: CurrentSession
    ) -> CurrentSession: ...


@runtime_checkable
class SessionRepository(Protocol):
    """Read port for the session-list rows (#7)."""

    async def list_all(self, session: AsyncSession) -> list[Session]: ...


@runtime_checkable
class SpeakerRepository(Protocol):
    """Persistence port for the speaker registry (#39/#40/#41)."""

    async def list_all(self, session: AsyncSession) -> list[Speaker]: ...

    async def get_by_id(
        self, session: AsyncSession, speaker_id: int
    ) -> Speaker | None: ...

    async def add(self, session: AsyncSession, speaker: Speaker) -> Speaker: ...

    async def update(self, session: AsyncSession, speaker: Speaker) -> Speaker: ...

    async def delete(self, session: AsyncSession, speaker_id: int) -> bool: ...
