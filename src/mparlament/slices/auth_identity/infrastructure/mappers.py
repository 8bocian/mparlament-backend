"""Mappers between the ``UserModel`` ORM row and domain/identity objects.

- ``to_domain`` → the slice's ``User`` aggregate (carries ``password_hash``).
- ``to_identity`` → the shared ``User`` value object (no credential) that RBAC/deps consume.
"""

from __future__ import annotations

from mparlament.shared.auth.user import User as IdentityUser
from mparlament.slices.auth_identity.domain.entities import Role
from mparlament.slices.auth_identity.domain.entities import User as DomainUser
from mparlament.slices.auth_identity.infrastructure.models import UserModel


def to_domain(row: UserModel) -> DomainUser:
    return DomainUser(
        id=row.id,
        username=row.username,
        password_hash=row.password_hash,
        name=row.name,
        club=row.club,
        role=Role(row.role),
        permissions=list(row.permissions or []),
        group=row.group,
    )


def to_identity(row: UserModel) -> IdentityUser:
    return IdentityUser(
        id=row.id,
        username=row.username,
        name=row.name,
        role=row.role,
        club=row.club,
        permissions=list(row.permissions or []),
        group=row.group,
    )
