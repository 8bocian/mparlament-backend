"""Query use cases for the users slice (read-only projections, doc 03).

Both reuse doc 02's ``UserRepository`` port — this slice adds no persistence (KISS). They map the
``User`` aggregate onto FE-facing DTOs that never carry the credential:
- ``ListUsersUseCase`` → ``UserPublic`` (spec #43, superset used to pick voting managers/users).
- ``ListMembersUseCase`` → ``MemberDTO`` (spec #42, ``{id, name, group}`` recipient picker).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.slices.auth_identity.application.dtos import UserPublic
from mparlament.slices.auth_identity.domain.ports import UserRepository
from mparlament.slices.users.application.dtos import MemberDTO


class ListUsersUseCase:
    """All users as ``UserPublic`` — no password (spec #43, C10)."""

    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def execute(self, session: AsyncSession) -> list[UserPublic]:
        users = await self._repo.list_all(session)
        return [UserPublic.model_validate(u) for u in users]


class ListMembersUseCase:
    """All users projected to ``{id, name, group}`` (spec #42, C9)."""

    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def execute(self, session: AsyncSession) -> list[MemberDTO]:
        users = await self._repo.list_all(session)
        return [MemberDTO.model_validate(u) for u in users]
