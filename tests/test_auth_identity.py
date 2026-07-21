"""Slice 02 — auth & identity: login + who-am-I (TDD checklist #1-9).

Order: domain unit (password hasher, jwt) → application use case → API integration
(``httpx.AsyncClient``). Endpoints #1 login, #2/#2b ``/auth/me``, #3 ``/current-user``.
Shapes and Polish messages come verbatim from BACKEND_SPEC.md §4 (AUTH) + CONVENTIONS C1/C6/C11.
"""

from __future__ import annotations

import json

import pytest

from mparlament.shared.auth.jwt_service import create_access_token, decode_token
from mparlament.shared.domain import UnauthorizedError
from mparlament.slices.auth_identity.application.use_cases import LoginUseCase
from mparlament.slices.auth_identity.infrastructure.password_hasher import (
    BcryptPasswordHasher,
)
from mparlament.slices.auth_identity.infrastructure.repository import (
    SqlAlchemyUserRepository,
)
from mparlament.slices.auth_identity.infrastructure.seed import DEV_USERS, seed_users

pytestmark = pytest.mark.anyio

ADMIN = DEV_USERS[0]  # TEST123, role=admin, club="TEST"


@pytest.fixture
async def seeded(async_session):
    """Insert the dev users into the shared in-memory DB (visible to the ASGI client)."""
    await seed_users(async_session)
    await async_session.commit()
    return DEV_USERS


def _assert_no_password(obj: object) -> None:
    """Recursively assert no password/password_hash leaks into a response body."""
    if isinstance(obj, dict):
        assert "password" not in obj
        assert "password_hash" not in obj
        for value in obj.values():
            _assert_no_password(value)
    elif isinstance(obj, list):
        for item in obj:
            _assert_no_password(item)


async def _login(client, username: str, password: str):
    return await client.post(
        "/api/auth/login", json={"username": username, "password": password}
    )


# --- domain / infrastructure unit ---------------------------------------


def test_password_hash_verified() -> None:  # checklist #9
    hasher = BcryptPasswordHasher()
    digest = hasher.hash("s3cret")
    assert digest != "s3cret"
    assert hasher.verify("s3cret", digest) is True
    assert hasher.verify("wrong", digest) is False


def test_jwt_encodes_user() -> None:  # checklist #8
    token = create_access_token(42)
    assert int(decode_token(token)["sub"]) == 42


# --- application use case ------------------------------------------------


async def test_login_use_case_bad_password(async_session, seeded) -> None:
    use_case = LoginUseCase(SqlAlchemyUserRepository(), BcryptPasswordHasher())
    with pytest.raises(UnauthorizedError) as exc:
        await use_case.execute(async_session, ADMIN["username"], "wrong-password")
    assert exc.value.message == "Nieprawidłowy login lub hasło"


async def test_login_use_case_success(async_session, seeded) -> None:
    use_case = LoginUseCase(SqlAlchemyUserRepository(), BcryptPasswordHasher())
    result = await use_case.execute(async_session, ADMIN["username"], ADMIN["password"])
    assert result.token
    assert result.user.username == ADMIN["username"]
    assert int(decode_token(result.token)["sub"]) == result.user.id


# --- API integration -----------------------------------------------------


async def test_login_success(client, seeded) -> None:  # checklist #1
    resp = await _login(client, ADMIN["username"], ADMIN["password"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["token"]
    user = body["user"]
    assert user["id"]
    assert user["name"] == ADMIN["name"]
    assert user["role"] == "admin"
    assert user["permissions"] == ADMIN["permissions"]
    _assert_no_password(body)


async def test_login_bad_credentials(client, seeded) -> None:  # checklist #2
    resp = await _login(client, ADMIN["username"], "nope")
    assert resp.status_code == 401
    assert resp.json() == {"message": "Nieprawidłowy login lub hasło"}


async def test_login_unknown_user(client, seeded) -> None:  # checklist #3
    resp = await _login(client, "GHOST999", "whatever")
    assert resp.status_code == 401
    assert resp.json() == {"message": "Nieprawidłowy login lub hasło"}


async def test_me_with_bearer(client, seeded) -> None:  # checklist #4
    token = (await _login(client, ADMIN["username"], ADMIN["password"])).json()["token"]
    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == ADMIN["username"]
    assert body["name"] == ADMIN["name"]
    assert body["role"] == "admin"
    assert body["club"] == ADMIN["club"]
    assert body["permissions"] == ADMIN["permissions"]
    _assert_no_password(body)


async def test_me_with_json_wrapped_bearer(client, seeded) -> None:  # checklist #5
    token = (await _login(client, ADMIN["username"], ADMIN["password"])).json()["token"]
    blob = json.dumps({"token": token, "expiresAt": 9999999999999})
    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {blob}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == ADMIN["username"]


async def test_me_without_token(client, seeded) -> None:  # checklist #6
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401
    assert resp.json() == {"message": "Wymagane uwierzytelnienie"}


async def test_current_user_wrapped(client, seeded) -> None:  # checklist #7
    token = (await _login(client, ADMIN["username"], ADMIN["password"])).json()["token"]
    resp = await client.get(
        "/api/current-user", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"user"}
    assert body["user"]["username"] == ADMIN["username"]
    _assert_no_password(body)

    anon = await client.get("/api/current-user")
    assert anon.status_code == 401
    assert anon.json() == {"message": "Wymagane uwierzytelnienie"}
