"""Slice 09 — groups list for voting recipients (TDD checklist #1-4).

``GET /api/groups`` (#41) supplies the groups used when choosing voting recipients. Groups are
derived from the distinct ``User.group`` values so their ids stay consistent with ``User.group``
and voting ``selectedGroups`` — the collections voting eligibility resolves against (C8). Shapes
come from BACKEND_SPEC.md §2 (Group), §4 (#41) + CONVENTIONS C8 (recipients), C10 (bare array).
"""

from __future__ import annotations

import pytest

from mparlament.slices.auth_identity.infrastructure.seed import DEV_USERS, seed_users
from mparlament.slices.votings.infrastructure.seed import DEV_VOTINGS, seed_votings

pytestmark = pytest.mark.anyio

ADMIN = DEV_USERS[0]  # TEST123, role=admin, group=None


@pytest.fixture
async def seeded(async_session):
    """Insert dev users into the shared in-memory DB (visible to the ASGI client)."""
    await seed_users(async_session)
    await async_session.commit()
    return DEV_USERS


@pytest.fixture
async def seeded_with_votings(async_session):
    """Users + votings so ``selectedGroups`` alignment (C8) can be asserted."""
    await seed_users(async_session)
    await seed_votings(async_session)
    await async_session.commit()


async def _bearer(client) -> dict[str, str]:
    resp = await client.post(
        "/api/auth/login",
        json={"username": ADMIN["username"], "password": ADMIN["password"]},
    )
    return {"Authorization": f"Bearer {resp.json()['token']}"}


# --- #41 GET /api/groups -------------------------------------------------


async def test_groups_bare_array(client, seeded) -> None:  # checklist #1
    resp = await client.get("/api/groups", headers=await _bearer(client))
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)  # bare array (C10)
    assert len(body) >= 1
    for item in body:
        assert {"id", "name"} <= item.keys()  # spec §2 Group {id, name}
    # Distinct non-null User.group values (A, B) become the groups.
    names = {g["name"] for g in body}
    assert names == {"A", "B"}


async def test_groups_membercount_optional(client, seeded) -> None:  # checklist #2
    """When included, ``memberCount`` equals the number of users in that group (C8 source)."""
    resp = await client.get("/api/groups", headers=await _bearer(client))
    by_id = {g["id"]: g for g in resp.json()}
    # Seeded users: MEMBER1→"A", MEMBER2→"B", TEST123→None.
    expected = {"A": 1, "B": 1}
    for gid, count in expected.items():
        assert by_id[gid]["memberCount"] == count


async def test_groups_ids_align_with_voting_selectedGroups(
    client, seeded_with_votings
) -> None:  # checklist #3
    """A seeded voting's ``selectedGroups`` all resolve to groups from ``/api/groups`` (C8)."""
    resp = await client.get("/api/groups", headers=await _bearer(client))
    group_ids = {g["id"] for g in resp.json()}
    selected = [
        gid
        for spec in DEV_VOTINGS
        for gid in spec["selected_groups"]
    ]
    assert selected  # the seed exercises groups-eligibility at least once
    for gid in selected:
        assert gid in group_ids  # eligibility stays resolvable (C8)


async def test_groups_requires_auth(client, seeded) -> None:  # checklist #4
    resp = await client.get("/api/groups")
    assert resp.status_code == 401
    assert resp.json() == {"message": "Wymagane uwierzytelnienie"}
