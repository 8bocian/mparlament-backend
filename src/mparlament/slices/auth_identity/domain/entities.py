"""Auth-identity domain entities (framework-free).

The ``User`` aggregate owns the credential (``password_hash``, never serialized) alongside the
identity fields the FE reads (spec §2 User, §8.7). It is distinct from the lightweight
``shared.auth.User`` value object, which carries no credential and is what RBAC/deps reason about
(CONVENTIONS C9). The ``is_admin`` rule lives once in ``shared.auth.rbac`` — do not duplicate it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

ALLOWED_PERMISSIONS = frozenset(
    {"MANAGE_VOTINGS", "MANAGE_RESOLUTIONS", "MANAGE_PARLIAMENTARIANS"}
)


class Role(StrEnum):
    """User role (spec §2 User)."""

    ADMIN = "admin"
    MARSHAL = "marshal"
    MEMBER = "member"


@dataclass
class User:
    """Login/author/manager/voter identity. ``password_hash`` is never serialized."""

    id: int
    username: str
    password_hash: str
    name: str = ""
    club: str | None = None
    role: Role = Role.MEMBER
    permissions: list[str] = field(default_factory=list)
    group: str | None = None

    def __post_init__(self) -> None:
        # Invariant (spec §8.7): role from the enum, permissions from the allowed set.
        self.role = Role(self.role)
        unknown = set(self.permissions) - ALLOWED_PERMISSIONS
        if unknown:
            raise ValueError(f"Unknown permissions: {sorted(unknown)}")
