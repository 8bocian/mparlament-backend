"""Auth-identity routes (spec §4 AUTH) — mounted under ``/api`` by the app factory.

- #1  POST /auth/login   (public)        → ``{token, user}``; 401 ``Nieprawidłowy login lub hasło``.
- #2/#2b GET /auth/me    (required auth)  → bare user; 401 ``Wymagane uwierzytelnienie``.
- #3  GET /current-user  (required auth)  → ``{user: <User>}`` (C6 wrapper).

``/me`` and ``/current-user`` use ``current_user`` (C2): the FE calls them both with and without a
token; when a token is present the tolerant bearer parser (C1) handles the localStorage-blob form,
and when it is absent ``current_user`` raises the 401 the FE treats as "logged out".
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.shared.api import wrapped
from mparlament.shared.auth import User as IdentityUser
from mparlament.shared.auth import current_user
from mparlament.shared.db import get_session
from mparlament.slices.auth_identity.application.dtos import (
    LoginRequest,
    LoginResponse,
    UserPublic,
)
from mparlament.slices.auth_identity.application.use_cases import (
    GetMeUseCase,
    LoginUseCase,
)
from mparlament.slices.auth_identity.infrastructure.password_hasher import (
    BcryptPasswordHasher,
)
from mparlament.slices.auth_identity.infrastructure.repository import (
    SqlAlchemyUserRepository,
)

router = APIRouter(tags=["auth"])

_login_use_case = LoginUseCase(SqlAlchemyUserRepository(), BcryptPasswordHasher())
_get_me = GetMeUseCase()


@router.post("/auth/login", response_model=LoginResponse)
async def login(
    body: LoginRequest, session: AsyncSession = Depends(get_session)
) -> LoginResponse:
    result = await _login_use_case.execute(session, body.username, body.password)
    return LoginResponse(token=result.token, user=UserPublic.model_validate(result.user))


@router.get("/auth/me", response_model=UserPublic)
async def me(user: IdentityUser = Depends(current_user)) -> UserPublic:
    return _get_me.execute(user)


@router.get("/current-user")
async def current_user_wrapped(
    user: IdentityUser = Depends(current_user),
) -> dict:
    return wrapped("user", _get_me.execute(user))
