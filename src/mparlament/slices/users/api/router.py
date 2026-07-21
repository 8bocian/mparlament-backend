"""Users-slice routes (spec §4 #42/#43) — mounted under ``/api`` by the app factory.

- #43 GET /users   (Bearer) → bare array ``[<User>]`` (``UserPublic``; no password).
- #42 GET /members (Bearer) → bare array ``[{id, name, group}]`` (``MemberDTO``).

Both require a valid identity (C2 ``current_user``); both return bare arrays (C10). The source is
the ``User`` collection only — never the parliamentarian registry (C9).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.shared.auth import User as IdentityUser
from mparlament.shared.auth import current_user
from mparlament.shared.db import get_session
from mparlament.slices.auth_identity.application.dtos import UserPublic
from mparlament.slices.auth_identity.infrastructure.repository import (
    SqlAlchemyUserRepository,
)
from mparlament.slices.users.application.dtos import MemberDTO
from mparlament.slices.users.application.use_cases import (
    ListMembersUseCase,
    ListUsersUseCase,
)

router = APIRouter(tags=["users"])

_repo = SqlAlchemyUserRepository()
_list_users = ListUsersUseCase(_repo)
_list_members = ListMembersUseCase(_repo)


@router.get("/users", response_model=list[UserPublic])
async def list_users(
    _: IdentityUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[UserPublic]:
    return await _list_users.execute(session)


@router.get("/members", response_model=list[MemberDTO])
async def list_members(
    _: IdentityUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[MemberDTO]:
    return await _list_members.execute(session)
