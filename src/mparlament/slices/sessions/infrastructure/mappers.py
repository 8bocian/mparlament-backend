"""Mappers between the sessions ORM rows and the framework-free domain objects.

The live-session JSON columns round-trip through the frozen value objects: ``to_current`` builds
value objects from stored dicts/lists; ``apply_current`` writes them back as plain JSON (via
``dataclasses.asdict``) so SQLite's ``JSON`` type can store them.
"""

from __future__ import annotations

from dataclasses import asdict

from mparlament.slices.sessions.domain.entities import (
    CurrentSession,
    Session,
    Speaker,
)
from mparlament.slices.sessions.infrastructure.models import (
    CurrentSessionModel,
    SessionModel,
    SpeakerModel,
)


def to_current(row: CurrentSessionModel) -> CurrentSession:
    return CurrentSession(
        id=row.id,
        title=row.title,
        status=row.status,
        active=row.active,
        date=row.date,
        start=row.start,
        startTime=row.start_time,
        end=row.end,
        endTime=row.end_time,
        currentSpeaker=row.current_speaker,
        currentPoint=row.current_point,
        schedule=row.schedule or [],
        zoContent=row.zo_content,
    )


def apply_current(row: CurrentSessionModel, current: CurrentSession) -> None:
    """Copy a domain ``CurrentSession`` onto an ORM row (JSON columns as plain dicts/lists)."""
    row.title = current.title
    row.status = current.status
    row.active = current.active
    row.date = current.date
    row.start = current.start
    row.start_time = current.startTime
    row.end = current.end
    row.end_time = current.endTime
    row.current_speaker = (
        asdict(current.currentSpeaker) if current.currentSpeaker else None
    )
    row.current_point = asdict(current.currentPoint) if current.currentPoint else None
    row.schedule = [asdict(item) for item in current.schedule]
    row.zo_content = current.zoContent


def to_session(row: SessionModel) -> Session:
    return Session(
        id=row.id,
        name=row.name,
        date=row.date,
        city=row.city,
        number=row.number,
        start=row.start,
        startTime=row.start_time,
        end=row.end,
        endTime=row.end_time,
    )


def to_speaker(row: SpeakerModel) -> Speaker:
    return Speaker(
        id=row.id,
        name=row.name,
        club=row.club,
        role=row.role,
        status=row.status or "waiting",
    )
