"""Domain services for the parliamentarians & clubs slice (doc 08).

Framework-free helpers that derive the read-time ``clubName``/``clubColor`` expansion and partition
the registry into affiliated / unaffiliated (spec #29, C10). Keeping this in the domain means the
use cases stay thin and the expansion rule has one home.
"""

from __future__ import annotations

from collections.abc import Iterable

from mparlament.slices.parliamentarians_clubs.domain.entities import (
    Club,
    Parliamentarian,
)


def expand(parliamentarian: Parliamentarian, club: Club | None) -> Parliamentarian:
    """Set ``clubName``/``clubColor`` on a parliamentarian from its club (``None`` ⇒ both null).

    Mutates and returns the same instance. The unaffiliated (or a dangling ``clubId``) get both
    fields cleared, so the FE always reads a consistent shape.
    """
    parliamentarian.clubName = club.name if club else None
    parliamentarian.clubColor = club.color if club else None
    return parliamentarian


def partition(
    parliamentarians: Iterable[Parliamentarian],
    clubs: Iterable[Club],
) -> tuple[list[Parliamentarian], list[Parliamentarian]]:
    """Expand every parliamentarian and split into ``(affiliated, unaffiliated)`` (spec #29).

    ``affiliated`` = those with a ``clubId``; ``unaffiliated`` = those without. The club lookup is
    built once from ``clubs``; a ``clubId`` pointing at a missing club degrades to unaffiliated-style
    null club fields but still counts as affiliated (it carries a non-null ``clubId``).
    """
    by_id = {club.id: club for club in clubs}
    affiliated: list[Parliamentarian] = []
    unaffiliated: list[Parliamentarian] = []
    for parliamentarian in parliamentarians:
        expand(parliamentarian, by_id.get(parliamentarian.clubId))
        if parliamentarian.is_affiliated:
            affiliated.append(parliamentarian)
        else:
            unaffiliated.append(parliamentarian)
    return affiliated, unaffiliated
