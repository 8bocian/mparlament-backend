"""Slice 03 — users & members read views (TDD checklist #1-4).

Read-only projections over the ``User`` collection (spec #42 ``GET /api/members``,
#43 ``GET /api/users``). Shapes come verbatim from BACKEND_SPEC.md §4 (#42/#43), §2
(User, Member) + CONVENTIONS C2 (Bearer required), C9 (User ≠ Parliamentarian), C10
(bare arrays). This slice reuses doc 02's ``UserRepository`` — no new persistence.
"""

from __future__ import annotations

import pytest

from mparlament.slices.auth_identity.infrastructure.seed import DEV_USERS, seed_users

pytestmark = pytest.mark.anyio

ADMIN = DEV_USERS[0]  # TEST123, role=admin, club="TEST", group=None


@pytest.fixture
async def seeded(async_session):
    """Insert the dev users into the shared in-memory DB (visible to the ASGI client)."""
    await seed_users(async_session)
    await async_session.commit()
    return DEV_USERS


async def _bearer(client) -> dict[str, str]:
    resp = await client.post(
        "/api/auth/login",
        json={"username": ADMIN["username"], "password": ADMIN["password"]},
    )
    return {"Authorization": f"Bearer {resp.json()['token']}"}


# --- #43 GET /api/users --------------------------------------------------


async def test_list_users_shape(client, seeded) -> None:  # checklist #1
    resp = await client.get("/api/users", headers=await _bearer(client))
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)  # bare array (C10)
    assert len(body) == len(DEV_USERS)
    for item in body:
        assert {"id", "name", "role"} <= item.keys()
        assert "password" not in item
        assert "password_hash" not in item
    # FE reads club/group for recipient/manager selection (doc #43).
    admin_item = next(u for u in body if u["username"] == ADMIN["username"])
    assert admin_item["role"] == "admin"
    assert admin_item["club"] == ADMIN["club"]
    assert "group" in admin_item


async def test_list_users_requires_auth(client, seeded) -> None:  # checklist #2
    resp = await client.get("/api/users")
    assert resp.status_code == 401
    assert resp.json() == {"message": "Wymagane uwierzytelnienie"}


# --- #42 GET /api/members ------------------------------------------------


async def test_list_members_shape(client, seeded) -> None:  # checklist #3
    resp = await client.get("/api/members", headers=await _bearer(client))
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)  # bare array (C10)
    assert len(body) == len(DEV_USERS)
    for item in body:
        assert set(item.keys()) == {"id", "name", "group"}  # exactly (spec §2 Member)


async def test_members_requires_auth(client, seeded) -> None:
    resp = await client.get("/api/members")
    assert resp.status_code == 401
    assert resp.json() == {"message": "Wymagane uwierzytelnienie"}


async def test_members_source_is_user_collection(client, seeded) -> None:  # checklist #4
    """/members projects the ``User`` collection, not the parliamentarian registry (C9).

    The ``Parliamentarian`` table is a distinct collection built in a later slice (doc 08);
    here we prove the source is exactly ``User`` by asserting the returned members correspond
    one-to-one to the seeded users — nothing from any other table leaks in.
    """
    resp = await client.get("/api/members", headers=await _bearer(client))
    members = resp.json()
    by_name = {m["name"]: m for m in members}
    # Every seeded User appears, carrying its own group value.
    for spec in DEV_USERS:
        assert spec["name"] in by_name
        assert by_name[spec["name"]]["group"] == spec["group"]
    # No extra rows from any other collection.
    assert len(members) == len(DEV_USERS)
