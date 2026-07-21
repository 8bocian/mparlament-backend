"""Slice 01 — shared auth: bearer parsing, JWT, deps, RBAC (TDD checklist #1-8)."""

from __future__ import annotations

import datetime as dt

import jwt
import pytest

from mparlament.shared.auth.bearer import extract_jwt
from mparlament.shared.auth.deps import current_user, optional_user
from mparlament.shared.auth.jwt_service import create_access_token, decode_token
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
from mparlament.shared.config import get_settings
from mparlament.shared.domain import PermissionDeniedError, UnauthorizedError

pytestmark = pytest.mark.anyio


# --- bearer (C1) ---------------------------------------------------------


def test_extract_jwt_raw() -> None:
    assert extract_jwt("Bearer abc.def.ghi") == "abc.def.ghi"


def test_extract_jwt_json_wrapped() -> None:
    assert extract_jwt('Bearer {"token":"abc","expiresAt":1}') == "abc"


def test_extract_jwt_missing_or_malformed() -> None:
    assert extract_jwt(None) is None
    assert extract_jwt("Basic x") is None
    assert extract_jwt("Bearer {bad") is None
    assert extract_jwt("Bearer ") is None


# --- jwt_service ---------------------------------------------------------


def test_jwt_roundtrip() -> None:
    token = create_access_token(7)
    assert decode_token(token)["sub"] == 7


def test_jwt_expired_raises() -> None:
    settings = get_settings()
    payload = {
        "sub": 7,
        "exp": dt.datetime.now(tz=dt.timezone.utc) - dt.timedelta(hours=1),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    with pytest.raises(jwt.PyJWTError):
        decode_token(token)


# --- deps (C2) -----------------------------------------------------------


async def test_optional_user_none_without_token() -> None:
    assert await optional_user(authorization=None, session=None) is None


async def test_current_user_401_without_token() -> None:
    with pytest.raises(UnauthorizedError) as exc:
        current_user(user=None)
    assert exc.value.message == "Wymagane uwierzytelnienie"


# --- rbac (C3) -----------------------------------------------------------


def _member(**kw: object) -> User:
    return User(id=kw.pop("id", 1), role="member", **kw)  # type: ignore[arg-type]


def test_is_admin() -> None:
    assert is_admin(User(id=1, role="admin"))
    assert is_admin(User(id=1, role="member", permissions=["MANAGE_VOTINGS"]))
    assert not is_admin(User(id=1, role="member"))
    assert not is_admin(User(id=1, role="marshal"))


def test_rbac_denies_member() -> None:
    member = _member()
    with pytest.raises(PermissionDeniedError) as exc:
        require_manage_votings(user=member)
    assert exc.value.message == "Brak uprawnień"

    # admin and a MANAGE_VOTINGS holder pass through.
    admin = User(id=2, role="admin")
    holder = User(id=3, role="member", permissions=["MANAGE_VOTINGS"])
    assert require_manage_votings(user=admin) is admin
    assert require_manage_votings(user=holder) is holder


def test_require_admin_or_marshal() -> None:
    marshal = User(id=1, role="marshal")
    assert require_admin_or_marshal(user=marshal) is marshal
    assert require_admin_or_marshal(user=User(id=2, role="admin")).id == 2
    with pytest.raises(PermissionDeniedError):
        require_admin_or_marshal(user=_member())


def test_require_manage_parliamentarians_and_resolutions() -> None:
    with pytest.raises(PermissionDeniedError):
        require_manage_parliamentarians(user=_member())
    with pytest.raises(PermissionDeniedError):
        require_manage_resolutions(user=_member())
    p = User(id=1, role="member", permissions=["MANAGE_PARLIAMENTARIANS"])
    r = User(id=2, role="member", permissions=["MANAGE_RESOLUTIONS"])
    assert require_manage_parliamentarians(user=p) is p
    assert require_manage_resolutions(user=r) is r


def test_require_authenticated_passthrough() -> None:
    m = _member()
    assert require_authenticated(user=m) is m


def test_can_manage_voting_via_managers() -> None:
    member = _member(id=42)

    class _Voting:
        managers = [42]

    assert can_manage_voting(member, _Voting())

    class _OtherVoting:
        managers = [99]

    assert not can_manage_voting(member, _OtherVoting())
    # admin manages any voting regardless of managers list.
    assert can_manage_voting(User(id=1, role="admin"), _OtherVoting())
