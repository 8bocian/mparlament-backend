"""The authenticated identity shared across slices.

CONVENTIONS C3/C9: ``User`` (login/authors/managers/voters) is a distinct concept from the
``Parliamentarian`` registry. The auth_identity slice (02) owns the ``User`` table and maps
its ORM rows onto this lightweight value object; the shared kernel defines the shape here so
RBAC guards and the auth dependencies can reason about identity without importing a slice
(dependency inversion — the auth_identity slice supplies rows via the ``UserReader`` port).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class User:
    """Authenticated user identity. Fields mirror the FE contract (spec §2, §8.7)."""

    id: int
    username: str = ""
    name: str = ""
    role: str = "member"  # admin | marshal | member
    club: str | None = None
    permissions: list[str] = field(default_factory=list)
    group: str | None = None
