"""FastAPI auth dependencies (CONVENTIONS C2).

- ``optional_user`` — best-effort identity; returns ``None`` on any failure, never raises.
  Used by reads that personalize when a token is present and serve public data otherwise.
- ``current_user`` — requires a valid identity; raises 401 (``Wymagane uwierzytelnienie``).
- ``identity_from_request`` — the token-optional-but-identity-needed chain (#21/#22/#28/#2b/#3):
  token identity first, then an explicit ``authorId``/``userId`` in the body, else 401.
"""

from __future__ import annotations

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.shared.auth.bearer import extract_jwt
from mparlament.shared.auth.jwt_service import decode_token
from mparlament.shared.auth.ports import get_user_reader
from mparlament.shared.auth.user import User
from mparlament.shared.db import get_session
from mparlament.shared.domain import UnauthorizedError


async def optional_user(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> User | None:
    """Resolve identity from the ``Authorization`` header, or ``None``. Never raises."""
    token = extract_jwt(authorization)
    if token is None:
        return None
    try:
        payload = decode_token(token)
        user_id = int(payload["sub"])
    except Exception:
        return None
    try:
        return await get_user_reader().get(session, user_id)
    except Exception:
        return None


def current_user(user: User | None = Depends(optional_user)) -> User:
    """Require a valid identity; raise 401 when absent."""
    if user is None:
        raise UnauthorizedError("Wymagane uwierzytelnienie")
    return user


async def identity_from_request(
    body_author_id: int | None = None,
    *,
    user: User | None = None,
    session: AsyncSession | None = None,
) -> User:
    """Identity chain for token-optional endpoints (C2): token -> body id -> 401.

    ``user`` is the already-resolved ``optional_user`` (token path). If that is absent and the
    request body carries an ``authorId``/``userId``, load that user via the registered reader.
    """
    if user is not None:
        return user
    if body_author_id is not None and session is not None:
        loaded = await get_user_reader().get(session, int(body_author_id))
        if loaded is not None:
            return loaded
    raise UnauthorizedError("Wymagane uwierzytelnienie")
