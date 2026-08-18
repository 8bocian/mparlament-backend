"""Read-time projections into the FE-facing shapes (spec §2, C10).

- ``parliamentarian_dict`` — the ``Parliamentarian`` object the FE reads, with the expanded
  ``clubName``/``clubColor`` (set by the domain service before projection).
- ``club_dict`` — the ``Club`` object the FE reads (``id, name, type, color``) plus ``members`` (the
  required reads emit ``members: []``; the FE computes counts from the parliamentarian list).
"""

from __future__ import annotations

from dataclasses import asdict

from mparlament.slices.parliamentarians_clubs.domain.entities import (
    Club,
    Parliamentarian,
)


def parliamentarian_dict(parliamentarian: Parliamentarian) -> dict:
    return {
        "id": parliamentarian.id,
        "firstName": parliamentarian.firstName,
        "lastName": parliamentarian.lastName,
        "clubId": parliamentarian.clubId,
        "clubName": parliamentarian.clubName,
        "clubColor": parliamentarian.clubColor,
        "functions": list(parliamentarian.functions or []),
        "commissions": list(parliamentarian.commissions or []),
    }


def club_dict(club: Club) -> dict:
    return {
        "id": club.id,
        "name": club.name,
        "type": club.type,
        "color": club.color,
        "members": [asdict(m) for m in (club.members or [])],
    }
