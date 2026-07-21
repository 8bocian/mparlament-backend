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
    """Lists/adds speaker-registry rows (#39/#40)."""

    async def list_all(self, session: AsyncSession) -> list[Speaker]:
        result = await session.execute(select(SpeakerModel).order_by(SpeakerModel.id))
        return [to_speaker(row) for row in result.scalars().all()]

    async def add(self, session: AsyncSession, speaker: Speaker) -> Speaker:
        row = SpeakerModel(name=speaker.name, club=speaker.club, role=speaker.role)
        session.add(row)
        await session.flush()
        return to_speaker(row)
