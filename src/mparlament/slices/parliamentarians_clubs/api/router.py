"""Parliamentarians & clubs routes (spec §4 #29-#36) — mounted under ``/api`` by the app factory.

Reads are Bearer-only; writes additionally require ``MANAGE_PARLIAMENTARIANS``/admin (C3, via the
``require_manage_parliamentarians`` guard → 403 ``Brak uprawnień``).

- #29 GET    /parliamentarians          (Bearer) → {parliamentarians, unaffiliated}
- #30 POST   /parliamentarians          (RBAC)   → upsert (C7); expanded club fields
- #31 PUT    /parliamentarians/:id       (RBAC)   → updated object; 404 when unknown
- #32 DELETE /parliamentarians/:id       (RBAC)   → {success:true}; unlinked from club
- #33 GET    /clubs                       (Bearer) → **bare array**
- #34 POST   /clubs                       (RBAC)   → 201 <Club> with id, members:[]
- #35 PUT    /clubs/:id                    (RBAC)   → updated <Club>; 404 when unknown
- #36 DELETE /clubs/:id                    (RBAC)   → {success:true}; members' clubId→null
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.shared.auth import User as IdentityUser
from mparlament.shared.auth import current_user, require_manage_parliamentarians
from mparlament.shared.db import get_session
from mparlament.slices.parliamentarians_clubs.application.dtos import (
    ClubBody,
    ParliamentarianBody,
)
from mparlament.slices.parliamentarians_clubs.application.use_cases import (
    CreateClubUseCase,
    DeleteClubUseCase,
    DeleteParliamentarianUseCase,
    ListClubsUseCase,
    ListParliamentariansUseCase,
    UpdateClubUseCase,
    UpdateParliamentarianUseCase,
    UpsertParliamentarianUseCase,
)
from mparlament.slices.parliamentarians_clubs.infrastructure.repository import (
    SqlAlchemyClubRepository,
    SqlAlchemyParliamentarianRepository,
)

router = APIRouter(tags=["parliamentarians-clubs"])

_parliamentarians = SqlAlchemyParliamentarianRepository()
_clubs = SqlAlchemyClubRepository()

_list_parliamentarians = ListParliamentariansUseCase(_parliamentarians, _clubs)
_upsert_parliamentarian = UpsertParliamentarianUseCase(_parliamentarians, _clubs)
_update_parliamentarian = UpdateParliamentarianUseCase(_parliamentarians, _clubs)
_delete_parliamentarian = DeleteParliamentarianUseCase(_parliamentarians, _clubs)

_list_clubs = ListClubsUseCase(_clubs)
_create_club = CreateClubUseCase(_clubs)
_update_club = UpdateClubUseCase(_clubs)
_delete_club = DeleteClubUseCase(_clubs)


# --- parliamentarians (#29-#32) --------------------------------------------


@router.get("/parliamentarians")
async def list_parliamentarians(
    user: IdentityUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await _list_parliamentarians.execute(session)


@router.post("/parliamentarians")
async def upsert_parliamentarian(
    body: ParliamentarianBody,
    user: IdentityUser = Depends(require_manage_parliamentarians),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await _upsert_parliamentarian.execute(session, body)


@router.put("/parliamentarians/{parliamentarian_id}")
async def update_parliamentarian(
    parliamentarian_id: int,
    body: ParliamentarianBody,
    user: IdentityUser = Depends(require_manage_parliamentarians),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await _update_parliamentarian.execute(session, parliamentarian_id, body)


@router.delete("/parliamentarians/{parliamentarian_id}")
async def delete_parliamentarian(
    parliamentarian_id: int,
    user: IdentityUser = Depends(require_manage_parliamentarians),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await _delete_parliamentarian.execute(session, parliamentarian_id)


# --- clubs (#33-#36) --------------------------------------------------------


@router.get("/clubs")
async def list_clubs(
    user: IdentityUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    return await _list_clubs.execute(session)


@router.post("/clubs", status_code=status.HTTP_201_CREATED)
async def create_club(
    body: ClubBody,
    user: IdentityUser = Depends(require_manage_parliamentarians),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await _create_club.execute(session, body)


@router.put("/clubs/{club_id}")
async def update_club(
    club_id: int,
    body: ClubBody,
    user: IdentityUser = Depends(require_manage_parliamentarians),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await _update_club.execute(session, club_id, body)


@router.delete("/clubs/{club_id}")
async def delete_club(
    club_id: int,
    user: IdentityUser = Depends(require_manage_parliamentarians),
    session: AsyncSession = Depends(get_session),
) -> dict:
    return await _delete_club.execute(session, club_id)
