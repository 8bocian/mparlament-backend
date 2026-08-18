"""Query use case for the groups slice (read-only projection, doc 09).

``ListGroupsUseCase`` maps the ``Group`` read model onto ``GroupDTO`` for ``GET /api/groups`` (#41,
bare array C10). No persistence of its own — the repository derives groups from the ``User``
collection so ids align with ``User.group`` and voting ``selectedGroups`` (C8).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.slices.groups_members.application.dtos import GroupDTO
from mparlament.slices.groups_members.domain.ports import GroupRepository


class ListGroupsUseCase:
    """All groups as ``GroupDTO`` — id, name, memberCount (spec #41, C10)."""

    def __init__(self, repo: GroupRepository) -> None:
        self._repo = repo

    async def execute(self, session: AsyncSession) -> list[GroupDTO]:
        groups = await self._repo.list_all(session)
        return [GroupDTO.model_validate(g) for g in groups]
