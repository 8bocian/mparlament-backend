"""Domain ports for the parliamentarians & clubs slice (dependency inversion).

Two persistence ports, both DB-agnostic (the adapters live in ``infrastructure``):

- ``ParliamentarianRepository`` — get/list/add/update/delete plus ``upsert`` (POST-as-upsert, C7).
- ``ClubRepository`` — get/list/add/update/delete; ``delete`` unlinks members (``clubId→null``, #36).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.slices.parliamentarians_clubs.domain.entities import (
    Club,
    Parliamentarian,
)


@runtime_checkable
class ParliamentarianRepository(Protocol):
    """Persistence port for the ``Parliamentarian`` aggregate (#29-#32)."""

    async def get_by_id(
        self, session: AsyncSession, parliamentarian_id: int
    ) -> Parliamentarian | None: ...

    async def list_all(self, session: AsyncSession) -> list[Parliamentarian]: ...

    async def add(
        self, session: AsyncSession, parliamentarian: Parliamentarian
    ) -> Parliamentarian: ...

    async def update(
        self, session: AsyncSession, parliamentarian: Parliamentarian
    ) -> Parliamentarian: ...

    async def upsert(
        self, session: AsyncSession, parliamentarian: Parliamentarian
    ) -> Parliamentarian: ...

    async def delete(
        self, session: AsyncSession, parliamentarian_id: int
    ) -> bool: ...


@runtime_checkable
class ClubRepository(Protocol):
    """Persistence port for the ``Club`` aggregate (#33-#36)."""

    async def get_by_id(
        self, session: AsyncSession, club_id: int
    ) -> Club | None: ...

    async def list_all(self, session: AsyncSession) -> list[Club]: ...

    async def add(self, session: AsyncSession, club: Club) -> Club: ...

    async def update(self, session: AsyncSession, club: Club) -> Club: ...

    async def delete(self, session: AsyncSession, club_id: int) -> bool:
        """Delete the club and unlink its members (``clubId→null``, #36)."""
        ...
