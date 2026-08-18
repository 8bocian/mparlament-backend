"""Parliamentarians & clubs domain (framework-free) — spec §2 (Parliamentarian, Club), doc 08.

The chamber registry is deliberately **distinct** from the ``User`` login collection (C9): these
aggregates never join or sync with users in v1.

- ``Parliamentarian`` — a member of the izba. Persists ``clubId`` (``None`` ⇒ niezrzeszony); the
  ``clubName``/``clubColor`` fields are **derived at read time** from the referenced club (never
  stored redundantly) by :func:`services.expand`. ``functions``/``commissions`` are free-text lists
  the FE reads/writes as-is.
- ``Club`` — a klub/koło/komitet. ``type`` is constrained to the allowed set (invariant). ``members``
  is derived from parliamentarians, not stored on the club (spec §6.1.7); it defaults to ``[]`` and
  the required reads emit ``members: []`` (the FE computes counts from the parliamentarian list).
- ``ClubMember`` — the shape a club's ``members[]`` would carry when expanded (spec §2 Club); kept
  for the optional handler-only #37/#38 and never populated by the required reads.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mparlament.shared.domain import ValidationError

KLUB = "klub"
KOLO = "koło"
KOMITET = "komitet"
CLUB_TYPES = frozenset({KLUB, KOLO, KOMITET})

_INVALID_TYPE = "Nieprawidłowy typ klubu"


# --- value object ----------------------------------------------------------


@dataclass
class ClubMember:
    """A club member as the FE would read it inside an expanded ``Club.members[]`` (spec §2)."""

    id: int | None = None
    firstName: str = ""
    lastName: str = ""
    functions: list = field(default_factory=list)
    commissions: list = field(default_factory=list)


# --- entities --------------------------------------------------------------


@dataclass
class Parliamentarian:
    """A member of the chamber registry (spec §2 Parliamentarian).

    ``clubName``/``clubColor`` are transient read-time expansions (see :func:`services.expand`);
    they are not persisted and stay ``None`` for the unaffiliated (``clubId is None``).
    """

    id: int | None = None
    firstName: str = ""
    lastName: str = ""
    clubId: int | None = None
    clubName: str | None = None
    clubColor: str | None = None
    functions: list = field(default_factory=list)
    commissions: list = field(default_factory=list)

    @property
    def is_affiliated(self) -> bool:
        return self.clubId is not None


@dataclass
class Club:
    """A klub/koło/komitet (spec §2 Club). ``type`` is validated against ``CLUB_TYPES``."""

    id: int | None = None
    name: str = ""
    type: str = KLUB
    color: str = ""
    members: list = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.type not in CLUB_TYPES:
            raise ValidationError(_INVALID_TYPE)
