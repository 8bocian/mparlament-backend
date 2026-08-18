"""Application use cases for the parliamentarians & clubs slice (doc 08).

Thin orchestration over the two repositories plus the domain expansion/partition service. RBAC and
identity are enforced in the router (C3); these stay unit-testable without FastAPI.

Parliamentarians:
- ``ListParliamentariansUseCase`` (#29) → ``{parliamentarians:[clubId!=null], unaffiliated:[...]}``.
- ``UpsertParliamentarianUseCase`` (#30) — POST-as-upsert (C7); expands club fields in the response.
- ``UpdateParliamentarianUseCase`` (#31 PUT) — 404 when the id is unknown.
- ``DeleteParliamentarianUseCase`` (#32) — removes the row (drops club membership); 404 when unknown.

Clubs:
- ``ListClubsUseCase`` (#33) → **bare array**; ``members:[]``.
- ``CreateClubUseCase`` (#34) / ``UpdateClubUseCase`` (#35) / ``DeleteClubUseCase`` (#36 unlink).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.shared.domain import NotFoundError
from mparlament.slices.parliamentarians_clubs.application.dtos import (
    ClubBody,
    ParliamentarianBody,
)
from mparlament.slices.parliamentarians_clubs.application.views import (
    club_dict,
    parliamentarian_dict,
)
from mparlament.slices.parliamentarians_clubs.domain.entities import Parliamentarian
from mparlament.slices.parliamentarians_clubs.domain.ports import (
    ClubRepository,
    ParliamentarianRepository,
)
from mparlament.slices.parliamentarians_clubs.domain.services import expand, partition

_PARLIAMENTARIAN_NOT_FOUND = "Nie znaleziono parlamentarzysty"
_CLUB_NOT_FOUND = "Nie znaleziono klubu"


# --- parliamentarians ------------------------------------------------------


class _ParliamentarianUseCase:
    """Shared wiring: parliamentarian repo + club repo (for read-time expansion)."""

    def __init__(
        self,
        parliamentarians: ParliamentarianRepository,
        clubs: ClubRepository,
    ) -> None:
        self._parliamentarians = parliamentarians
        self._clubs = clubs

    async def _expanded(
        self, session: AsyncSession, parliamentarian: Parliamentarian
    ) -> dict:
        """Expand ``clubName``/``clubColor`` from ``clubId`` and project to the FE shape."""
        club = (
            await self._clubs.get_by_id(session, parliamentarian.clubId)
            if parliamentarian.clubId is not None
            else None
        )
        expand(parliamentarian, club)
        return parliamentarian_dict(parliamentarian)


class ListParliamentariansUseCase(_ParliamentarianUseCase):
    """Registry partitioned by affiliation (spec #29, C10)."""

    async def execute(self, session: AsyncSession) -> dict:
        parliamentarians = await self._parliamentarians.list_all(session)
        clubs = await self._clubs.list_all(session)
        affiliated, unaffiliated = partition(parliamentarians, clubs)
        return {
            "parliamentarians": [parliamentarian_dict(p) for p in affiliated],
            "unaffiliated": [parliamentarian_dict(p) for p in unaffiliated],
        }


class UpsertParliamentarianUseCase(_ParliamentarianUseCase):
    """POST-as-upsert (spec #30, C7): update in place when ``id`` matches, else create."""

    async def execute(
        self, session: AsyncSession, body: ParliamentarianBody
    ) -> dict:
        saved = await self._parliamentarians.upsert(
            session, body.to_parliamentarian()
        )
        return await self._expanded(session, saved)


class UpdateParliamentarianUseCase(_ParliamentarianUseCase):
    """PUT update (spec #31): 404 ``Nie znaleziono parlamentarzysty`` when the id is unknown."""

    async def execute(
        self,
        session: AsyncSession,
        parliamentarian_id: int,
        body: ParliamentarianBody,
    ) -> dict:
        existing = await self._parliamentarians.get_by_id(
            session, parliamentarian_id
        )
        if existing is None:
            raise NotFoundError(_PARLIAMENTARIAN_NOT_FOUND)
        saved = await self._parliamentarians.update(
            session, body.to_parliamentarian(id=parliamentarian_id)
        )
        return await self._expanded(session, saved)


class DeleteParliamentarianUseCase(_ParliamentarianUseCase):
    """Delete + unlink from club (spec #32): 404 when unknown, else ``{success:true}``."""

    async def execute(
        self, session: AsyncSession, parliamentarian_id: int
    ) -> dict:
        deleted = await self._parliamentarians.delete(session, parliamentarian_id)
        if not deleted:
            raise NotFoundError(_PARLIAMENTARIAN_NOT_FOUND)
        return {"success": True}


# --- clubs -----------------------------------------------------------------


class ListClubsUseCase:
    """All clubs as a **bare array** (spec #33, C10); ``members:[]``."""

    def __init__(self, clubs: ClubRepository) -> None:
        self._clubs = clubs

    async def execute(self, session: AsyncSession) -> list[dict]:
        clubs = await self._clubs.list_all(session)
        return [club_dict(c) for c in clubs]


class CreateClubUseCase:
    """Create a club (spec #34): 201 ``<Club>`` with ``id`` and ``members:[]``."""

    def __init__(self, clubs: ClubRepository) -> None:
        self._clubs = clubs

    async def execute(self, session: AsyncSession, body: ClubBody) -> dict:
        created = await self._clubs.add(session, body.to_club())
        return club_dict(created)


class UpdateClubUseCase:
    """Update a club (spec #35): 404 ``Nie znaleziono klubu`` when the id is unknown."""

    def __init__(self, clubs: ClubRepository) -> None:
        self._clubs = clubs

    async def execute(
        self, session: AsyncSession, club_id: int, body: ClubBody
    ) -> dict:
        existing = await self._clubs.get_by_id(session, club_id)
        if existing is None:
            raise NotFoundError(_CLUB_NOT_FOUND)
        updated = await self._clubs.update(session, body.to_club(id=club_id))
        return club_dict(updated)


class DeleteClubUseCase:
    """Delete a club and unlink its members (spec #36): 404 when unknown, else ``{success:true}``."""

    def __init__(self, clubs: ClubRepository) -> None:
        self._clubs = clubs

    async def execute(self, session: AsyncSession, club_id: int) -> dict:
        deleted = await self._clubs.delete(session, club_id)
        if not deleted:
            raise NotFoundError(_CLUB_NOT_FOUND)
        return {"success": True}
