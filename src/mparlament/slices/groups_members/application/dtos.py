"""Pydantic DTO for the groups slice (spec §2 Group, #41).

``GroupDTO`` is the ``{id, name, memberCount}`` shape the FE reads from ``GET /api/groups``. ``id``
mirrors the ``User.group`` value it derives from (a string here) so voting ``selectedGroups`` stay
resolvable (C8). ``memberCount`` is always included; the FE tolerates it (``group.memberCount || 0``).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class GroupDTO(BaseModel):
    """``{id, name, memberCount}`` — voting-recipient group projection."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    memberCount: int = 0
