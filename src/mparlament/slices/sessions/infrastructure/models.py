"""SQLAlchemy models for the sessions slice.

- ``current_session`` — a singleton row (id=1, C6) holding the live sitting's scalar fields plus
  its document-shaped members (``currentSpeaker``, ``currentPoint``, ``schedule``) as JSON columns.
  JSON avoids premature normalization (YAGNI) while matching the FE's document reads/writes.
- ``sessions`` — the session-list rows (#7).
- ``speakers`` — the speaker registry (#39/#40).

Registered on ``Base.metadata`` via ``shared.models_registry`` so create_all/Alembic see them.
"""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from mparlament.shared.db import Base


class CurrentSessionModel(Base):
    __tablename__ = "current_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    date: Mapped[str | None] = mapped_column(String, nullable=True)
    start: Mapped[str | None] = mapped_column(String, nullable=True)
    start_time: Mapped[str | None] = mapped_column(String, nullable=True)
    end: Mapped[str | None] = mapped_column(String, nullable=True)
    end_time: Mapped[str | None] = mapped_column(String, nullable=True)
    current_speaker: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    current_point: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    schedule: Mapped[list] = mapped_column(JSON, default=list)
    zo_content: Mapped[str] = mapped_column(String, default="")


class SessionModel(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, default="")
    date: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    number: Mapped[str | None] = mapped_column(String, nullable=True)
    start: Mapped[str | None] = mapped_column(String, nullable=True)
    start_time: Mapped[str | None] = mapped_column(String, nullable=True)
    end: Mapped[str | None] = mapped_column(String, nullable=True)
    end_time: Mapped[str | None] = mapped_column(String, nullable=True)


class SpeakerModel(Base):
    __tablename__ = "speakers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, default="")
    club: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str | None] = mapped_column(String, nullable=True)
