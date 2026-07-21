"""Pydantic DTOs for the users slice (spec §2 Member, #42).

The users-list projection reuses ``UserPublic`` from doc 02 (spec §2 User, #43). ``MemberDTO``
is the thinner recipient-picker shape ``{id, name, group}`` the FE reads from ``GET /api/members``.
Neither carries a password (C10).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class MemberDTO(BaseModel):
    """``{id, name, group}`` — voting-recipient projection over the ``User`` collection."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    group: str | None = None
