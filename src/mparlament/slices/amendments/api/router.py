"""Amendments-slice routes (spec §4 #23-#28) — mounted under ``/api`` by the app factory.

- #23/b GET  /resolutions/:slug/amendments               (public; slug **or** id, C5) → composite
- #24   POST /resolutions/:slug/amendments               (public; identity from body, C2) → 201
- #25   GET  /resolutions/:slug/amendments/:amendmentId   (public) → composite; 404 poprawki
- #26   GET  /amendments                                  (Bearer) → **bare array**
- #27   GET  /amendments/:id                              (Bearer) → {data:{...,resolution}}
- #28   POST /amendments/:id/withdraw                     (identity chain C2; author-only) → 200

Route order matters: the concrete ``/amendments/:id/withdraw`` is declared before the catch-all
``/amendments/:id`` so the id param never swallows it. The ``/resolutions/...`` routes live here
too (they share the ``resolutions`` prefix but are a distinct path from the resolutions router's
``/resolutions/:slug`` detail route, so FastAPI matches them independently).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.shared.auth import User as IdentityUser
from mparlament.shared.auth import current_user, identity_from_request, optional_user
from mparlament.shared.db import get_session
from mparlament.slices.amendments.application.dtos import (
    AmendmentCreateBody,
    WithdrawBody,
)
from mparlament.slices.amendments.application.use_cases import (
    CreateAmendmentUseCase,
    GetAmendmentUnderResolutionUseCase,
    GetAmendmentUseCase,
    ListAmendmentsUseCase,
    ListResolutionAmendmentsUseCase,
    WithdrawAmendmentUseCase,
)
from mparlament.slices.amendments.infrastructure.repository import (
    SqlAlchemyAmendmentRepository,
)
from mparlament.slices.resolutions.infrastructure.repository import (
    SqlAlchemyResolutionRepository,
    SqlAlchemySessionLookup,
)

router = APIRouter(tags=["amendments"])

_amendments = SqlAlchemyAmendmentRepository()
_resolutions = SqlAlchemyResolutionRepository()
_sessions = SqlAlchemySessionLookup()

_list_by_resolution = ListResolutionAmendmentsUseCase(_amendments, _resolutions, _sessions)
_create = CreateAmendmentUseCase(_amendments, _resolutions, _sessions)
_get_under_resolution = GetAmendmentUnderResolutionUseCase(
    _amendments, _resolutions, _sessions
)
_list = ListAmendmentsUseCase(_amendments, _resolutions, _sessions)
_get = GetAmendmentUseCase(_amendments, _resolutions, _sessions)
_withdraw = WithdrawAmendmentUseCase(_amendments, _resolutions, _sessions)


# --- amendments-under-a-resolution (#23/#23b/#24/#25) -----------------------


@router.get("/resolutions/{param}/amendments")
async def list_resolution_amendments(
    param: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await _list_by_resolution.execute(session, param)


@router.post(
    "/resolutions/{param}/amendments", status_code=status.HTTP_201_CREATED
)
async def create_amendment(
    param: str,
    body: AmendmentCreateBody,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await _create.execute(session, param, body)


@router.get("/resolutions/{param}/amendments/{amendment_id}")
async def get_amendment_under_resolution(
    param: str,
    amendment_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await _get_under_resolution.execute(session, param, amendment_id)


# --- top-level amendments (#26/#27/#28) -------------------------------------


@router.get("/amendments")
async def list_amendments(
    user: IdentityUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await _list.execute(session)


@router.post("/amendments/{amendment_id}/withdraw")
async def withdraw_amendment(
    amendment_id: int,
    body: WithdrawBody,
    user: IdentityUser | None = Depends(optional_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    actor = await identity_from_request(
        body.authorId if body.authorId is not None else body.userId,
        user=user,
        session=session,
    )
    return await _withdraw.execute(session, amendment_id, actor.id, body.reason)


@router.get("/amendments/{amendment_id}")
async def get_amendment(
    amendment_id: int,
    user: IdentityUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await _get.execute(session, amendment_id)
