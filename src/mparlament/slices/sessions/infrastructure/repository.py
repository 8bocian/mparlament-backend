"""SQLAlchemy adapters implementing the sessions domain ports."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.slices.sessions.domain.entities import (
    CurrentSession,
    Session,
    Speaker,
)
from mparlament.slices.sessions.infrastructure.mappers import (
    apply_current,
    to_current,
    to_session,
    to_speaker,
)
from mparlament.slices.sessions.infrastructure.models import (
    CurrentSessionModel,
    SessionModel,
    SpeakerModel,
)

_CURRENT_ID = 1  # the singleton live-session row (C6)


class SqlAlchemyCurrentSessionRepository:
    """Loads/persists the singleton live session."""

    async def get(self, session: AsyncSession) -> CurrentSession | None:
        row = await session.get(CurrentSessionModel, _CURRENT_ID)
        return to_current(row) if row else None

    async def save(
        self, session: AsyncSession, current: CurrentSession
    ) -> CurrentSession:
        row = await session.get(CurrentSessionModel, _CURRENT_ID)
        if row is None:
            row = CurrentSessionModel(id=_CURRENT_ID)
            session.add(row)
        apply_current(row, current)
        await session.flush()
        return to_current(row)


class SqlAlchemySessionRepository:
    """Lists the session-list rows (#7)."""

    async def list_all(self, session: AsyncSession) -> list[Session]:
        result = await session.execute(select(SessionModel).order_by(SessionModel.id))
        return [to_session(row) for row in result.scalars().all()]


class SqlAlchemySpeakerRepository:
    """CRUD on speaker-registry rows (#39/#40/#41)."""

    async def list_all(self, session: AsyncSession) -> list[Speaker]:
        result = await session.execute(select(SpeakerModel).order_by(SpeakerModel.id))
        return [to_speaker(row) for row in result.scalars().all()]

    async def get_by_id(self, session: AsyncSession, speaker_id: int) -> Speaker | None:
        row = await session.get(SpeakerModel, speaker_id)
        return to_speaker(row) if row else None

    async def add(self, session: AsyncSession, speaker: Speaker) -> Speaker:
        row = SpeakerModel(
            name=speaker.name,
            club=speaker.club,
            role=speaker.role,
            status=speaker.status,
        )
        session.add(row)
        await session.flush()
        return to_speaker(row)

    async def update(self, session: AsyncSession, speaker: Speaker) -> Speaker:
        row = await session.get(SpeakerModel, speaker.id)
        if row is None:
            raise KeyError(speaker.id)
        row.name = speaker.name
        row.club = speaker.club
        row.role = speaker.role
        row.status = speaker.status
        await session.flush()
        return to_speaker(row)

    async def delete(self, session: AsyncSession, speaker_id: int) -> bool:
        row = await session.get(SpeakerModel, speaker_id)
        if row is None:
            return False
        await session.delete(row)
        await session.flush()
        return True
