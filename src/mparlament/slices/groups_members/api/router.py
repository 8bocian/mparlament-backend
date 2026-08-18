"""Groups-slice route (spec §4 #41) — mounted under ``/api`` by the app factory.

- #41 GET /groups (Bearer) → bare array ``[{id, name, memberCount}]`` (``GroupDTO``).

Requires a valid identity (C2 ``current_user``); returns a bare array (C10). Groups are derived
from the ``User`` collection so their ids resolve voting ``selectedGroups`` eligibility (C8).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.shared.auth import User as IdentityUser
from mparlament.shared.auth import current_user
from mparlament.shared.db import get_session
from mparlament.slices.groups_members.application.dtos import GroupDTO
from mparlament.slices.groups_members.application.use_cases import ListGroupsUseCase
from mparlament.slices.groups_members.infrastructure.repository import (
    SqlAlchemyGroupRepository,
)

router = APIRouter(tags=["groups"])

_repo = SqlAlchemyGroupRepository()
_list_groups = ListGroupsUseCase(_repo)


@router.get("/groups", response_model=list[GroupDTO])
async def list_groups(
    _: IdentityUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[GroupDTO]:
    return await _list_groups.execute(session)
