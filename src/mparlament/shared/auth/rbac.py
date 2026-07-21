"""Role/permission guards (CONVENTIONS C3).

``is_admin`` mirrors the FE rule (``role=="admin"`` or any ``MANAGE_*`` permission). Each
``require_*`` is a FastAPI dependency that depends on :func:`current_user` and raises 403
(``Brak uprawnień``) on denial — usable directly in tests by passing ``user=`` explicitly.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends

from mparlament.shared.auth.deps import current_user
from mparlament.shared.auth.user import User
from mparlament.shared.domain import PermissionDeniedError

_DENIED = "Brak uprawnień"


def is_admin(user: User) -> bool:
    """Admin by role, or holder of any ``MANAGE_*`` permission (FE parity)."""
    return user.role == "admin" or any(p.startswith("MANAGE_") for p in user.permissions)


def _has(user: User, permission: str) -> bool:
    return is_admin(user) or permission in user.permissions


def can_manage_voting(user: User, voting: Any) -> bool:
    """Admin / ``MANAGE_VOTINGS`` holder, or a user listed in ``voting.managers``."""
    if is_admin(user) or "MANAGE_VOTINGS" in user.permissions:
        return True
    managers = getattr(voting, "managers", None) or []
    manager_ids = {getattr(m, "id", m) for m in managers}
    return user.id in manager_ids


def require_authenticated(user: User = Depends(current_user)) -> User:
    """Any authenticated user (identity already enforced by ``current_user``)."""
    return user


def require_manage_votings(user: User = Depends(current_user)) -> User:
    if not _has(user, "MANAGE_VOTINGS"):
        raise PermissionDeniedError(_DENIED)
    return user


def require_manage_resolutions(user: User = Depends(current_user)) -> User:
    if not _has(user, "MANAGE_RESOLUTIONS"):
        raise PermissionDeniedError(_DENIED)
    return user


def require_manage_parliamentarians(user: User = Depends(current_user)) -> User:
    if not _has(user, "MANAGE_PARLIAMENTARIANS"):
        raise PermissionDeniedError(_DENIED)
    return user


def require_admin_or_marshal(user: User = Depends(current_user)) -> User:
    if not (is_admin(user) or user.role == "marshal"):
        raise PermissionDeniedError(_DENIED)
    return user
