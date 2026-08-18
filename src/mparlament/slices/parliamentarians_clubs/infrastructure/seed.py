"""Dev seed for the parliamentarians & clubs slice (doc 08).

Two clubs of different types/colors plus several parliamentarians — some affiliated, some
unaffiliated (``club_id=None``). Idempotent: skips ids already present so it is safe at startup and
in tests. Does not commit. Independent of every other slice (C9: registry is separate from users).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.slices.parliamentarians_clubs.infrastructure.models import (
    ClubModel,
    ParliamentarianModel,
)

DEV_CLUBS: list[dict] = [
    {"id": 1, "name": "Klub Obywatelski", "type": "klub", "color": "#f59e0b"},
    {"id": 2, "name": "Koło Niezależnych", "type": "koło", "color": "#2563eb"},
]

DEV_PARLIAMENTARIANS: list[dict] = [
    {
        "id": 1,
        "first_name": "Anna",
        "last_name": "Kowalska",
        "club_id": 1,
        "functions": ["Przewodnicząca"],
        "commissions": ["Komisja Edukacji"],
    },
    {
        "id": 2,
        "first_name": "Piotr",
        "last_name": "Nowak",
        "club_id": 1,
        "functions": [],
        "commissions": ["Komisja Budżetu"],
    },
    {
        "id": 3,
        "first_name": "Maria",
        "last_name": "Wiśniewska",
        "club_id": 2,
        "functions": ["Sekretarz"],
        "commissions": [],
    },
    {
        "id": 4,
        "first_name": "Tomasz",
        "last_name": "Lewandowski",
        "club_id": None,
        "functions": [],
        "commissions": [],
    },
]


async def seed_parliamentarians_clubs(session: AsyncSession) -> None:
    """Insert any missing ``DEV_CLUBS`` then ``DEV_PARLIAMENTARIANS``. Does not commit."""
    existing_clubs = set(
        (await session.execute(select(ClubModel.id))).scalars().all()
    )
    for spec in DEV_CLUBS:
        if spec["id"] not in existing_clubs:
            session.add(ClubModel(**spec))
    await session.flush()

    existing_p = set(
        (await session.execute(select(ParliamentarianModel.id))).scalars().all()
    )
    for spec in DEV_PARLIAMENTARIANS:
        if spec["id"] not in existing_p:
            session.add(ParliamentarianModel(**spec))
    await session.flush()
