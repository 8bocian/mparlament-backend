"""Votings-slice routes (spec §4 #8-#16) — mounted under ``/api`` by the app factory. All Bearer.

- #8  GET    /votings              → bare array + computed (C10)
- #9  GET    /votings/:id          → full voting + eligible/voted/notVoted lists; 404
- #10 POST   /votings              (MANAGE_VOTINGS/admin) → 201 created + id
- #11 PUT    /votings/:id          (MANAGE_VOTINGS or manager) → updated object
- #12 POST   /votings/:id/vote     → {vote, message?}; 400 already voted; 404
- #13 POST   /votings/:id/activate (manage) → {success, message, voting}; status=active
- #14 POST   /votings/:id/archive  (manage) → {success, voting}; status=archived + linked cascade
- #15 POST   /votings/:id/attachments (manage, multipart) → {success:true} (fire-and-forget)
- #16 DELETE /votings/:id          (manage) → {success:true}

RBAC (C3): #10 needs MANAGE_VOTINGS; #11/#13/#14/#15/#16 also accept a user listed in the voting's
``managers`` (``can_manage_voting``) — enforced per-request since it depends on the loaded voting.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.shared.auth import User as IdentityUser
from mparlament.shared.auth import (
    can_manage_voting,
    current_user,
    require_manage_votings,
)
from mparlament.shared.db import get_session
from mparlament.shared.domain import NotFoundError, PermissionDeniedError
from mparlament.shared.storage import LocalDiskStorage
from mparlament.slices.votings.application.dtos import (
    ActivateInput,
    VoteInput,
    VotingWriteInput,
)
from mparlament.slices.votings.application.use_cases import (
    ActivateVotingUseCase,
    AddAttachmentsUseCase,
    ArchiveVotingUseCase,
    CastVoteUseCase,
    CreateVotingUseCase,
    DeleteVotingUseCase,
    GetVotingUseCase,
    ListVotingsUseCase,
    UpdateVotingUseCase,
)
from mparlament.slices.resolutions.infrastructure.repository import (
    ResolutionLinkedItemStatusUpdater,
)
from mparlament.slices.votings.infrastructure.repository import (
    SqlAlchemyUserDirectory,
    SqlAlchemyVoteRepository,
    SqlAlchemyVotingRepository,
)

router = APIRouter(tags=["votings"])

_votings = SqlAlchemyVotingRepository()
_votes = SqlAlchemyVoteRepository()
_directory = SqlAlchemyUserDirectory()
_storage = LocalDiskStorage()
_linked = ResolutionLinkedItemStatusUpdater()  # doc 06 cascade: archive → resolution status.

_list = ListVotingsUseCase(_votings, _votes, _directory)
_get = GetVotingUseCase(_votings, _votes, _directory)
_create = CreateVotingUseCase(_votings, _votes, _directory)
_update = UpdateVotingUseCase(_votings, _votes, _directory)
_cast = CastVoteUseCase(_votings, _votes, _directory)
_activate = ActivateVotingUseCase(_votings, _votes, _directory)
_archive = ArchiveVotingUseCase(_votings, _votes, _directory, _linked)
_attach = AddAttachmentsUseCase(_votings, _votes, _directory, _storage)
_delete = DeleteVotingUseCase(_votings, _votes, _directory)

_NOT_FOUND = "Nie znaleziono głosowania"


async def _ensure_can_manage(
    session: AsyncSession, voting_id: int, user: IdentityUser
) -> None:
    """Manager-aware guard (C3): admin / MANAGE_VOTINGS / listed manager, else 403 (404 if absent)."""
    voting = await _votings.get(session, voting_id)
    if voting is None:
        raise NotFoundError(_NOT_FOUND)
    if not can_manage_voting(user, voting):
        raise PermissionDeniedError("Brak uprawnień")


@router.get("/votings")
async def list_votings(
    userId: int | None = None,  # noqa: N803 - FE query param (spec #8); accepted, filtering deferred
    role: str | None = None,
    user: IdentityUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await _list.execute(session, user.id)


@router.get("/votings/{voting_id}")
async def get_voting(
    voting_id: int,
    user: IdentityUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await _get.execute(session, voting_id, user.id)


@router.post("/votings", status_code=status.HTTP_201_CREATED)
async def create_voting(
    payload: VotingWriteInput,
    user: IdentityUser = Depends(require_manage_votings),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await _create.execute(session, payload.to_domain(), user.id)


@router.put("/votings/{voting_id}")
async def update_voting(
    voting_id: int,
    payload: VotingWriteInput,
    user: IdentityUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await _ensure_can_manage(session, voting_id, user)
    return await _update.execute(
        session, voting_id, payload.to_domain(voting_id=voting_id), user.id
    )


@router.post("/votings/{voting_id}/vote")
async def cast_vote(
    voting_id: int,
    payload: VoteInput,
    user: IdentityUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await _cast.execute(session, voting_id, user.id, payload.vote)


@router.post("/votings/{voting_id}/activate")
async def activate_voting(
    voting_id: int,
    payload: ActivateInput,
    user: IdentityUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await _ensure_can_manage(session, voting_id, user)
    return await _activate.execute(
        session,
        voting_id,
        payload.startTime,
        payload.endTime,
        payload.duration,
        payload.delay,
        user.id,
    )


@router.post("/votings/{voting_id}/archive")
async def archive_voting(
    voting_id: int,
    user: IdentityUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await _ensure_can_manage(session, voting_id, user)
    return await _archive.execute(session, voting_id, user.id)


@router.post("/votings/{voting_id}/attachments")
async def add_attachments(
    voting_id: int,
    request: Request,
    user: IdentityUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await _ensure_can_manage(session, voting_id, user)
    form = await request.form()
    files: list[tuple[str, bytes, str | None]] = []
    for key, value in form.multi_items():
        if not key.startswith("attachment"):
            continue
        if hasattr(value, "read"):  # an UploadFile
            data = await value.read()
            files.append((value.filename or key, data, value.content_type))
    return await _attach.execute(session, voting_id, files)


@router.delete("/votings/{voting_id}")
async def delete_voting(
    voting_id: int,
    user: IdentityUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    await _ensure_can_manage(session, voting_id, user)
    return await _delete.execute(session, voting_id)
