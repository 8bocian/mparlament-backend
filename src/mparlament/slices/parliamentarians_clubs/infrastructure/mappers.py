"""Mappers between the ORM rows and the framework-free domain objects (doc 08).

The read-time ``clubName``/``clubColor`` are **not** persisted, so ``to_parliamentarian`` leaves
them ``None`` (the domain service fills them in). ``functions``/``commissions`` round-trip as plain
JSON lists. ``members`` is never stored on the club, so ``to_club`` reads it back as ``[]``.
"""

from __future__ import annotations

from mparlament.slices.parliamentarians_clubs.domain.entities import (
    Club,
    Parliamentarian,
)
from mparlament.slices.parliamentarians_clubs.infrastructure.models import (
    ClubModel,
    ParliamentarianModel,
)


def to_parliamentarian(row: ParliamentarianModel) -> Parliamentarian:
    return Parliamentarian(
        id=row.id,
        firstName=row.first_name,
        lastName=row.last_name,
        clubId=row.club_id,
        functions=list(row.functions or []),
        commissions=list(row.commissions or []),
    )


def apply_parliamentarian(
    row: ParliamentarianModel, parliamentarian: Parliamentarian
) -> None:
    """Copy a domain ``Parliamentarian`` onto an ORM row (club expansion is not persisted)."""
    row.first_name = parliamentarian.firstName
    row.last_name = parliamentarian.lastName
    row.club_id = parliamentarian.clubId
    row.functions = list(parliamentarian.functions or [])
    row.commissions = list(parliamentarian.commissions or [])


def to_club(row: ClubModel) -> Club:
    return Club(id=row.id, name=row.name, type=row.type, color=row.color)


def apply_club(row: ClubModel, club: Club) -> None:
    row.name = club.name
    row.type = club.type
    row.color = club.color
