"""Pydantic DTOs for the auth-identity slice.

``UserPublic`` is the FE-facing user shape (spec §2 User) — **never carries a password**.
It maps from either the slice ``User`` aggregate or the shared identity ``User`` (both expose
the same public attributes), so ``model_validate`` works on both.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    username: str
    password: str


class UserPublic(BaseModel):
    """``{id, username, name, role, club, permissions}`` — no password (spec §4.1, C10)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    name: str
    role: str
    club: str | None = None
    permissions: list[str]


class LoginResponse(BaseModel):
    token: str
    user: UserPublic
