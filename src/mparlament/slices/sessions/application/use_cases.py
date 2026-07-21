"""Application use cases for the sessions slice (doc 04).

Read/write orchestration over the domain ports; DTO mapping happens in the API layer. RBAC is
enforced in the router (C3) via ``require_admin_or_marshal`` — the write use cases stay purely
about state so they remain unit-testable without FastAPI.

Realtime note (doc 10 / spec §5): ``UpdateCurrentSessionUseCase`` and ``AddSpeakerUseCase`` are
the natural emit points for ``scheduleUpdated`` / ``speakerUpdated`` / ``zoContentUpdated``.
Emitting a Socket.IO event later is a one-line addition here — deliberately not implemented now
(YAGNI); see the TODO markers.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.slices.sessions.domain.entities import (
    CurrentSession,
    Session,
    Speaker,
)
from mparlament.slices.sessions.domain.ports import (
    CurrentSessionRepository,
    SessionRepository,
    SpeakerRepository,
)


class GetCurrentSessionUseCase:
    """Return the live session; a neutral empty object when none exists (never 404, per doc)."""

    def __init__(self, repo: CurrentSessionRepository) -> None:
        self._repo = repo

    async def execute(self, session: AsyncSession) -> CurrentSession:
        current = await self._repo.get(session)
        return current if current is not None else CurrentSession()


class UpdateCurrentSessionUseCase:
    """Partial-merge the live session (spec #5). ``patch`` holds only the FE-sent keys."""

    def __init__(self, repo: CurrentSessionRepository) -> None:
        self._repo = repo

    async def execute(self, session: AsyncSession, patch: dict) -> CurrentSession:
        current = await self._repo.get(session) or CurrentSession()
        merged = current.with_patch(patch)
        saved = await self._repo.save(session, merged)
        # TODO(doc 10): emit scheduleUpdated / speakerUpdated / zoContentUpdated here.
        return saved


class ListSessionsUseCase:
    """All session-list rows (#7)."""

    def __init__(self, repo: SessionRepository) -> None:
        self._repo = repo

    async def execute(self, session: AsyncSession) -> list[Session]:
        return await self._repo.list_all(session)


class ListSpeakersUseCase:
    """All speaker-registry rows (#39)."""

    def __init__(self, repo: SpeakerRepository) -> None:
        self._repo = repo

    async def execute(self, session: AsyncSession) -> list[Speaker]:
        return await self._repo.list_all(session)


class AddSpeakerUseCase:
    """Append a speaker to the registry (#40)."""

    def __init__(self, repo: SpeakerRepository) -> None:
        self._repo = repo

    async def execute(
        self, session: AsyncSession, name: str, club: str | None, role: str | None
    ) -> Speaker:
        speaker = await self._repo.add(
            session, Speaker(id=None, name=name, club=club, role=role)
        )
        # TODO(doc 10): emit speakerUpdated here.
        return speaker
