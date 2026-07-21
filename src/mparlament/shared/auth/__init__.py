"""Shared authentication & authorization kernel (CONVENTIONS C1-C3)."""

from __future__ import annotations

from mparlament.shared.auth.bearer import extract_jwt
from mparlament.shared.auth.deps import (
    current_user,
    identity_from_request,
    optional_user,
)
from mparlament.shared.auth.jwt_service import create_access_token, decode_token
from mparlament.shared.auth.ports import UserReader, get_user_reader, set_user_reader
from mparlament.shared.auth.rbac import (
    can_manage_voting,
    is_admin,
    require_admin_or_marshal,
    require_authenticated,
    require_manage_parliamentarians,
    require_manage_resolutions,
    require_manage_votings,
)
from mparlament.shared.auth.user import User

__all__ = [
    "User",
    "UserReader",
    "can_manage_voting",
    "create_access_token",
    "current_user",
    "decode_token",
    "extract_jwt",
    "get_user_reader",
    "identity_from_request",
    "is_admin",
    "optional_user",
    "require_admin_or_marshal",
    "require_authenticated",
    "require_manage_parliamentarians",
    "require_manage_resolutions",
    "require_manage_votings",
    "set_user_reader",
]
