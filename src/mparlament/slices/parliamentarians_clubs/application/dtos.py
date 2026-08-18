"""Pydantic DTOs for the parliamentarians & clubs slice (spec §4 #30/#31, #34/#35).

- ``ParliamentarianBody`` — the JSON the FE POSTs/PUTs (#30/#31). Carries an optional ``id`` so
  POST can act as an upsert (C7); the router/UC decides create-vs-update.
- ``ClubBody`` — ``{name, type, color}`` for #34/#35. ``type`` is validated in the domain ``Club``.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from mparlament.slices.parliamentarians_clubs.domain.entities import (
    Club,
    Parliamentarian,
)


class ParliamentarianBody(BaseModel):
    """The JSON body of ``POST /api/parliamentarians`` (#30) and ``PUT .../:id`` (#31)."""

    model_config = ConfigDict(extra="ignore")

    id: int | None = None
    firstName: str = ""
    lastName: str = ""
    clubId: int | None = None
    functions: list[str] = []
    commissions: list[str] = []

    def to_parliamentarian(self, *, id: int | None = None) -> Parliamentarian:
        """Build a domain ``Parliamentarian``; ``id`` override wins (the PUT path id, #31)."""
        return Parliamentarian(
            id=id if id is not None else self.id,
            firstName=self.firstName,
            lastName=self.lastName,
            clubId=self.clubId,
            functions=list(self.functions),
            commissions=list(self.commissions),
        )


class ClubBody(BaseModel):
    """The JSON body of ``POST /api/clubs`` (#34) and ``PUT /api/clubs/:id`` (#35)."""

    model_config = ConfigDict(extra="ignore")

    name: str = ""
    type: str = "klub"
    color: str = ""

    def to_club(self, *, id: int | None = None) -> Club:
        """Build a domain ``Club`` (validates ``type``). ``id`` set on the update path (#35)."""
        return Club(id=id, name=self.name, type=self.type, color=self.color)

    def as_kwargs(self) -> dict[str, Any]:
        return {"name": self.name, "type": self.type, "color": self.color}
