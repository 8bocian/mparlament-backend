"""Application use cases for the sessions slice (doc 04).

Read/write orchestration over the domain ports; DTO mapping happens in the API layer. RBAC is
enforced in the router (C3) via ``require_admin_or_marshal`` — the write use cases stay purely
about state so they remain unit-testable without FastAPI.

Realtime note (doc 10 / spec §5): ``UpdateCurrentSessionUseCase`` and ``AddSpeakerUseCase`` emit
``scheduleUpdated`` / ``speakerUpdated`` / ``zoContentUpdated`` via the injected
:class:`EventPublisher` port. The update use case emits only the events whose keys the FE actually
sent in the partial patch. Payloads are plain JSON (value objects flattened via ``asdict``) so they
match the FE listeners exactly. The default publisher is a no-op until Socket.IO is wired.
"""

from __future__ import annotations

from dataclasses import asdict

from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.shared.realtime import EventPublisher, NullEventPublisher
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

    def __init__(
        self,
        repo: CurrentSessionRepository,
        publisher: EventPublisher | None = None,
    ) -> None:
        self._repo = repo
        self._publisher = publisher or NullEventPublisher()

    async def execute(self, session: AsyncSession, patch: dict) -> CurrentSession:
        current = await self._repo.get(session) or CurrentSession()
        merged = current.with_patch(patch)
        saved = await self._repo.save(session, merged)
        await self._emit(patch, saved)
        return saved

    async def _emit(self, patch: dict, saved: CurrentSession) -> None:
        """Emit one event per FE-sent live-session key (doc 10 / spec §5)."""
        if "schedule" in patch:
            await self._publisher.emit(
                "scheduleUpdated", [asdict(item) for item in saved.schedule]
            )
        if "currentSpeaker" in patch:
            speaker = asdict(saved.currentSpeaker) if saved.currentSpeaker else None
            await self._publisher.emit("speakerUpdated", speaker)
        if "zoContent" in patch:
            await self._publisher.emit("zoContentUpdated", saved.zoContent)


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

    def __init__(
        self,
        repo: SpeakerRepository,
        publisher: EventPublisher | None = None,
    ) -> None:
        self._repo = repo
        self._publisher = publisher or NullEventPublisher()

    async def execute(
        self, session: AsyncSession, name: str, club: str | None, role: str | None
    ) -> Speaker:
        speaker = await self._repo.add(
            session, Speaker(id=None, name=name, club=club, role=role)
        )
        # The FE ``newSpeaker`` listener reads {name, club, role, time}; the registry entity has
        # no ``time`` (that lives on the live session's CurrentSpeaker), so it is null here.
        await self._publisher.emit(
            "speakerUpdated",
            {"name": speaker.name, "club": speaker.club, "role": speaker.role, "time": None},
        )
        return speaker
