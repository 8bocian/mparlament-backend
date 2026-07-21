"""Use cases for the auth-identity slice.

``LoginUseCase`` verifies credentials and mints a JWT (spec #1); a bad username *or* password
raises the same ``UnauthorizedError`` so we never leak which field was wrong (checklist #2/#3).
``GetMeUseCase`` is a thin mapper from a resolved identity to the public DTO (spec #2/#2b/#3).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.shared.auth.jwt_service import create_access_token
from mparlament.shared.auth.user import User as IdentityUser
from mparlament.shared.domain import UnauthorizedError
from mparlament.slices.auth_identity.application.dtos import UserPublic
from mparlament.slices.auth_identity.domain.entities import User
from mparlament.slices.auth_identity.domain.ports import PasswordHasher, UserRepository

_BAD_CREDENTIALS = "Nieprawidłowy login lub hasło"


@dataclass
class LoginResult:
    token: str
    user: User


class LoginUseCase:
    def __init__(self, repo: UserRepository, hasher: PasswordHasher) -> None:
        self._repo = repo
        self._hasher = hasher

    async def execute(
        self, session: AsyncSession, username: str, password: str
    ) -> LoginResult:
        user = await self._repo.get_by_username(session, username)
        if user is None or not self._hasher.verify(password, user.password_hash):
            raise UnauthorizedError(_BAD_CREDENTIALS)
        return LoginResult(token=create_access_token(user.id), user=user)


class GetMeUseCase:
    """Map an already-resolved identity into the public DTO (identity done by deps, C2)."""

    def execute(self, user: IdentityUser | User) -> UserPublic:
        return UserPublic.model_validate(user)
