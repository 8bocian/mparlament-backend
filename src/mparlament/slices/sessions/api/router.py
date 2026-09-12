"""Sessions-slice routes (spec §4 #4-#7, #39/#40) — mounted under ``/api`` by the app factory.

- #4 GET  /session/current   (Bearer)  ┐ two routes, one handler — identical C6 superset object
- #6 GET  /sessions/current  (Bearer)  ┘
- #5 PUT  /session/current   (Bearer, admin/marshal) — partial merge, returns full object
- #7 GET  /sessions          (public)  → bare array [{id, name, date, city}] (C10)
- #39 GET /speakers          (Bearer)  → bare array [{name, club, role}] (C10)
- #40 POST /speakers         (Bearer, admin/marshal) → 201 {id, name, club, role}
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.shared.auth import User as IdentityUser
from mparlament.shared.auth import current_user, require_admin_or_marshal
from mparlament.shared.db import get_session
from mparlament.shared.domain import NotFoundError
from mparlament.shared.realtime import deferred_event_publisher
from mparlament.slices.sessions.application.dtos import (
    AddSpeakerInput,
    CurrentSessionDTO,
    SessionListDTO,
    SetSpeakerStatusInput,
    SpeakerDTO,
    UpdateCurrentSessionInput,
    UpdateSpeakerInput,
)
from mparlament.slices.sessions.application.use_cases import (
    AddSpeakerUseCase,
    DeleteSpeakerUseCase,
    GetCurrentSessionUseCase,
    ListSessionsUseCase,
    ListSpeakersUseCase,
    SetSpeakerStatusUseCase,
    UpdateCurrentSessionUseCase,
    UpdateSpeakerUseCase,
)
from mparlament.slices.sessions.infrastructure.repository import (
    SqlAlchemyCurrentSessionRepository,
    SqlAlchemySessionRepository,
    SqlAlchemySpeakerRepository,
)

router = APIRouter(tags=["sessions"])

_current_repo = SqlAlchemyCurrentSessionRepository()
_session_repo = SqlAlchemySessionRepository()
_speaker_repo = SqlAlchemySpeakerRepository()

_get_current = GetCurrentSessionUseCase(_current_repo)
_update_current = UpdateCurrentSessionUseCase(_current_repo, deferred_event_publisher)
_list_sessions = ListSessionsUseCase(_session_repo)
_list_speakers = ListSpeakersUseCase(_speaker_repo)
_add_speaker = AddSpeakerUseCase(_speaker_repo, deferred_event_publisher)
_update_speaker = UpdateSpeakerUseCase(_speaker_repo)
_delete_speaker = DeleteSpeakerUseCase(_speaker_repo)
_set_speaker_status = SetSpeakerStatusUseCase(_speaker_repo)


@router.get("/session/current", response_model=CurrentSessionDTO)
@router.get("/sessions/current", response_model=CurrentSessionDTO)
async def get_current_session(
    _: IdentityUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> CurrentSessionDTO:
    current = await _get_current.execute(session)
    return CurrentSessionDTO.model_validate(current)


@router.put("/session/current", response_model=CurrentSessionDTO)
async def update_current_session(
    payload: UpdateCurrentSessionInput,
    _: IdentityUser = Depends(require_admin_or_marshal),
    session: AsyncSession = Depends(get_session),
) -> CurrentSessionDTO:
    patch = payload.model_dump(exclude_unset=True)
    updated = await _update_current.execute(session, patch)
    return CurrentSessionDTO.model_validate(updated)


@router.get("/sessions", response_model=list[SessionListDTO])
async def list_sessions(
    session: AsyncSession = Depends(get_session),
) -> list[SessionListDTO]:
    sessions = await _list_sessions.execute(session)
    return [SessionListDTO.model_validate(s) for s in sessions]


@router.get("/speakers", response_model=list[SpeakerDTO])
async def list_speakers(
    _: IdentityUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[SpeakerDTO]:
    speakers = await _list_speakers.execute(session)
    return [SpeakerDTO.model_validate(s) for s in speakers]


@router.post(
    "/speakers", response_model=SpeakerDTO, status_code=status.HTTP_201_CREATED
)
async def add_speaker(
    payload: AddSpeakerInput,
    _: IdentityUser = Depends(require_admin_or_marshal),
    session: AsyncSession = Depends(get_session),
) -> SpeakerDTO:
    speaker = await _add_speaker.execute(
        session, payload.name, payload.club, payload.role
    )
    return SpeakerDTO.model_validate(speaker)


# --- speaker CRUD (#41) -----------------------------------------------------


@router.put("/speakers/{speaker_id}", response_model=SpeakerDTO)
async def update_speaker(
    speaker_id: int,
    payload: UpdateSpeakerInput,
    _: IdentityUser = Depends(require_admin_or_marshal),
    session: AsyncSession = Depends(get_session),
) -> SpeakerDTO:
    speaker = await _update_speaker.execute(
        session,
        speaker_id,
        payload.name,
        payload.club,
        payload.role,
        payload.status,
    )
    return SpeakerDTO.model_validate(speaker)


@router.put("/speakers", response_model=SpeakerDTO)
async def update_speaker_no_url(
    payload: UpdateSpeakerInput,
    _: IdentityUser = Depends(require_admin_or_marshal),
    session: AsyncSession = Depends(get_session),
) -> SpeakerDTO:
    """FE-friendly variant (SessionDetails.jsx calls PUT /api/speakers with id in body)."""
    if payload.id is None:
        raise NotFoundError("Brak id mówcy")
    speaker = await _update_speaker.execute(
        session,
        payload.id,
        payload.name,
        payload.club,
        payload.role,
        payload.status,
    )
    return SpeakerDTO.model_validate(speaker)


@router.patch("/speakers/{speaker_id}/status", response_model=SpeakerDTO)
async def set_speaker_status(
    speaker_id: int,
    payload: SetSpeakerStatusInput,
    _: IdentityUser = Depends(require_admin_or_marshal),
    session: AsyncSession = Depends(get_session),
) -> SpeakerDTO:
    speaker = await _set_speaker_status.execute(session, speaker_id, payload.status)
    return SpeakerDTO.model_validate(speaker)


@router.delete("/speakers/{speaker_id}")
async def delete_speaker(
    speaker_id: int,
    _: IdentityUser = Depends(require_admin_or_marshal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await _delete_speaker.execute(session, speaker_id)
