"""Domain port for the groups slice (dependency inversion).

The application layer depends on this Protocol; the concrete adapter lives in ``infrastructure``
and derives the groups from the ``User`` collection (distinct ``group`` values + counts) so ids
stay consistent with ``User.group`` and voting ``selectedGroups`` (C8, C9).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.slices.groups_members.domain.entities import Group


@runtime_checkable
class GroupRepository(Protocol):
    """Persistence port for the ``Group`` read model (#41)."""

    async def list_all(self, session: AsyncSession) -> list[Group]: ...
