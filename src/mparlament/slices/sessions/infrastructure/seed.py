"""Dev seed for the sessions slice (spec §2 / doc 04).

Inserts one live session (``status="TRWA"`` with a schedule, current speaker and ZO text), a few
session-list rows, and a couple of speakers. Idempotent: skips anything already present so it is
safe at startup and in tests. Does not commit.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.slices.sessions.infrastructure.models import (
    CurrentSessionModel,
    SessionModel,
    SpeakerModel,
)

_CURRENT_ID = 1

DEV_SESSIONS: list[dict] = [
    {"id": 1, "name": "I Posiedzenie", "date": "19.09.2026", "city": "Warszawa"},
    {"id": 2, "name": "II Posiedzenie", "date": "17.10.2026", "city": "Kraków"},
    {"id": 3, "name": "III Posiedzenie", "date": "21.11.2026", "city": "Gdańsk"},
]

DEV_SPEAKERS: list[dict] = [
    {"name": "Jan Kowalski", "club": "TEST", "role": "Marszałek"},
    {"name": "Anna Nowak", "club": "KO", "role": "Poseł"},
]


async def seed_sessions(session: AsyncSession) -> None:
    """Insert the live session, session-list rows and speakers if missing (no commit)."""
    if await session.get(CurrentSessionModel, _CURRENT_ID) is None:
        session.add(
            CurrentSessionModel(
                id=_CURRENT_ID,
                title="I Posiedzenie Parlamentu Młodych RP",
                status="TRWA",
                active=True,
                date="19.09.2026",
                start="10:00",
                start_time="2026-09-19T10:00:00",
                end="16:00",
                end_time="2026-09-19T16:00:00",
                current_speaker={
                    "name": "Jan Kowalski",
                    "club": "TEST",
                    "role": "Marszałek",
                    "time": "10:15",
                },
                current_point={
                    "number": "1",
                    "title": "Otwarcie posiedzenia",
                    "type": "formal",
                },
                schedule=[
                    {"time": "10:00", "title": "Otwarcie posiedzenia", "status": "done"},
                    {"time": "10:30", "title": "Debata programowa", "status": "active"},
                    {"time": "12:00", "title": "Głosowania", "status": "waiting"},
                ],
                zo_content="Tryb ZO: brak aktywnych zgłoszeń.",
            )
        )

    existing_sessions = set(
        (await session.execute(select(SessionModel.id))).scalars().all()
    )
    for spec in DEV_SESSIONS:
        if spec["id"] in existing_sessions:
            continue
        session.add(SessionModel(**spec))

    existing_speakers = set(
        (await session.execute(select(SpeakerModel.name))).scalars().all()
    )
    for spec in DEV_SPEAKERS:
        if spec["name"] in existing_speakers:
            continue
        session.add(SpeakerModel(**spec))

    await session.flush()
