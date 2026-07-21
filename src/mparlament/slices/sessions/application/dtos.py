"""Pydantic DTOs for the sessions slice (shapes verbatim from BACKEND_SPEC.md §4).

``CurrentSessionDTO`` serializes the full C6 superset (both aliases return it identically).
``UpdateCurrentSessionInput`` is an all-optional patch: the router reads only the keys the FE
actually sent (``model_dump(exclude_unset=True)``) so the merge stays partial (spec #5).
``SessionListDTO`` is the ``{id, name, date, city}`` list row (#7); ``SpeakerDTO`` /
``AddSpeakerInput`` cover the speaker registry (#39/#40).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CurrentSpeakerDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    club: str | None = None
    role: str | None = None
    time: str | None = None


class AgendaPointDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    number: str | None = None
    title: str | None = None
    type: str | None = None


class ScheduleItemDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    time: str | None = None
    title: str | None = None
    status: str = "waiting"


class CurrentSessionDTO(BaseModel):
    """The live-session superset object (spec §2 CurrentSession, C6)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    status: str
    active: bool
    date: str | None = None
    start: str | None = None
    startTime: str | None = None
    end: str | None = None
    endTime: str | None = None
    currentSpeaker: CurrentSpeakerDTO | None = None
    currentPoint: AgendaPointDTO | None = None
    schedule: list[ScheduleItemDTO] = []
    zoContent: str = ""


class UpdateCurrentSessionInput(BaseModel):
    """Partial PUT body (spec #5). All optional; only sent keys are merged."""

    model_config = ConfigDict(extra="ignore")

    title: str | None = None
    status: str | None = None
    active: bool | None = None
    date: str | None = None
    start: str | None = None
    startTime: str | None = None
    end: str | None = None
    endTime: str | None = None
    currentSpeaker: CurrentSpeakerDTO | None = None
    currentPoint: AgendaPointDTO | None = None
    schedule: list[ScheduleItemDTO] | None = None
    zoContent: str | None = None


class SessionListDTO(BaseModel):
    """A session-list row (spec §2 Session, #7)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    date: str | None = None
    city: str | None = None


class SpeakerDTO(BaseModel):
    """Speaker registry row (#39/#40)."""

    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    name: str
    club: str | None = None
    role: str | None = None


class AddSpeakerInput(BaseModel):
    """``POST /api/speakers`` body (#40)."""

    name: str
    club: str | None = None
    role: str | None = None
