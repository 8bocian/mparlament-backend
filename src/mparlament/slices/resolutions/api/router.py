"""Resolutions-slice routes (spec §4 #17-#22) — mounted under ``/api`` by the app factory.

- #17  GET    /resolutions                    (optional auth, C2) → {resolutions:[...]}
- #18/b GET   /resolutions/:slug              (optional auth; slug **or** id, C5) → detail; 404
- #19  POST   /resolutions                    (public, multipart via XHR, C14) → 201 created
- #20  GET    /resolutions/session/:sessionId (public) → {resolutions, sessionId, count}
- #21  POST   /resolutions/:id/sign           (identity via C2) → {success:true}; 400 already signed
- #22  DELETE /resolutions/:id/sign           (identity via C2) → {success, message}; 403 author; 404

Route order matters: the specific ``/session/...`` and ``/:id/sign`` paths are declared before the
catch-all ``/resolutions/:slug`` detail route so the slug param never swallows them.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.shared.auth import User as IdentityUser
from mparlament.shared.auth import (
    current_user,
    optional_user,
    require_admin_or_marshal,
)
from mparlament.shared.db import get_session
from mparlament.shared.storage import LocalDiskStorage
from mparlament.slices.resolutions.application.use_cases import (
    CreateResolutionUseCase,
    DeleteResolutionUseCase,
    GetResolutionUseCase,
    ListResolutionsUseCase,
    ListSessionResolutionsUseCase,
    SignResolutionUseCase,
    UnsignResolutionUseCase,
)
from mparlament.slices.resolutions.infrastructure.repository import (
    SqlAlchemyResolutionRepository,
    SqlAlchemySessionLookup,
    SqlAlchemySignatureRepository,
    SqlAlchemyUserDirectory,
)

router = APIRouter(tags=["resolutions"])

_resolutions = SqlAlchemyResolutionRepository()
_signatures = SqlAlchemySignatureRepository()
_directory = SqlAlchemyUserDirectory()
_sessions = SqlAlchemySessionLookup()
_storage = LocalDiskStorage()

_list = ListResolutionsUseCase(_resolutions, _signatures, _directory, _sessions)
_get = GetResolutionUseCase(_resolutions, _signatures, _directory, _sessions)
_create = CreateResolutionUseCase(
    _resolutions, _signatures, _directory, _sessions, _storage
)
_sign = SignResolutionUseCase(_resolutions, _signatures, _directory, _sessions)
_unsign = UnsignResolutionUseCase(_resolutions, _signatures, _directory, _sessions)
_delete = DeleteResolutionUseCase(_resolutions, _signatures, _directory, _sessions)
_session_list = ListSessionResolutionsUseCase(
    _resolutions, _signatures, _directory, _sessions
)


@router.get("/resolutions")
async def list_resolutions(
    user: IdentityUser | None = Depends(optional_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await _list.execute(session)


@router.post("/resolutions", status_code=status.HTTP_201_CREATED)
async def create_resolution(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    form = await request.form()
    upload = form.get("file")
    file_bytes = b""
    upload_name = None
    if upload is not None and hasattr(upload, "read"):
        file_bytes = await upload.read()
        upload_name = upload.filename
    data_json = form.get("data")
    return await _create.execute(session, file_bytes, upload_name, data_json)


@router.get("/resolutions/session/{session_id}")
async def list_session_resolutions(
    session_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await _session_list.execute(session, session_id)


@router.post("/resolutions/{resolution_id}/sign")
async def sign_resolution(
    resolution_id: int,
    user: IdentityUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await _sign.execute(session, resolution_id, user.id)


@router.delete("/resolutions/{resolution_id}/sign")
async def unsign_resolution(
    resolution_id: int,
    user: IdentityUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await _unsign.execute(session, resolution_id, user.id)


@router.delete("/resolutions/{resolution_id}")
async def delete_resolution(
    resolution_id: int,
    user: IdentityUser = Depends(require_admin_or_marshal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await _delete.execute(session, resolution_id)


@router.get("/resolutions/{param}")
async def get_resolution(
    param: str,
    user: IdentityUser | None = Depends(optional_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await _get.execute(session, param, user.id if user else None)
