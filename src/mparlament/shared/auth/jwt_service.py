"""JWT minting/verification (thin wrapper over PyJWT).

HS256 with the secret/TTL from settings. ``sub`` carries the integer user id. ``decode_token``
raises :class:`jwt.PyJWTError` (incl. ``ExpiredSignatureError``) on any invalid/expired token;
callers in ``deps`` translate that into "no identity".
"""

from __future__ import annotations

import datetime as dt

import jwt

from mparlament.shared.config import get_settings


def create_access_token(user_id: int, *, ttl_hours: int | None = None) -> str:
    """Mint an HS256 access token for ``user_id`` (``sub``), expiring after ``ttl_hours``."""
    settings = get_settings()
    ttl = settings.jwt_ttl_hours if ttl_hours is None else ttl_hours
    now = dt.datetime.now(tz=dt.timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + dt.timedelta(hours=ttl),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Verify + decode a token. Raises :class:`jwt.PyJWTError` if invalid or expired.

    ``verify_sub`` is disabled because we carry an integer ``sub`` (the user id); PyJWT >= 2.10
    otherwise rejects a non-string subject. Expiry and signature are still verified.
    """
    settings = get_settings()
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        options={"verify_sub": False},
    )
