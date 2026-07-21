"""Domain ports for the auth-identity slice (dependency inversion).

The application layer depends on these Protocols; concrete adapters live in ``infrastructure``.
``UserRepository`` loads/lists the ``User`` aggregate; ``PasswordHasher`` wraps the credential
primitive (passlib/bcrypt) so the use cases never import it directly.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.slices.auth_identity.domain.entities import User


@runtime_checkable
class UserRepository(Protocol):
    """Persistence port for the ``User`` aggregate."""

    async def get_by_id(self, session: AsyncSession, user_id: int) -> User | None: ...

    async def get_by_username(
        self, session: AsyncSession, username: str
    ) -> User | None: ...

    async def list_all(self, session: AsyncSession) -> list[User]: ...


@runtime_checkable
class PasswordHasher(Protocol):
    """Credential hashing/verification port."""

    def hash(self, raw: str) -> str: ...

    def verify(self, raw: str, hashed: str) -> bool: ...
