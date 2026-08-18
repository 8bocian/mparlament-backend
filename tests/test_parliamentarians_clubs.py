"""Slice 08 — parliamentarians & clubs: partitioned registry + club CRUD + RBAC.

Shapes come verbatim from BACKEND_SPEC.md §2 (Parliamentarian, Club), §4 (#29-#36) + CONVENTIONS
C3 (MANAGE_PARLIAMENTARIANS on writes), C7 (POST-as-upsert), C9 (registry separate from users),
C10 (``{parliamentarians, unaffiliated}`` + bare clubs array).

Layering (CLAUDE.md): domain unit (type invariant, expand/partition) → API integration mirroring
the doc's TDD checklist.
"""

from __future__ import annotations

import pytest

from mparlament.shared.domain import ValidationError
from mparlament.slices.auth_identity.infrastructure.seed import DEV_USERS, seed_users
from mparlament.slices.parliamentarians_clubs.domain.entities import (
    Club,
    Parliamentarian,
)
from mparlament.slices.parliamentarians_clubs.domain.services import expand, partition
from mparlament.slices.parliamentarians_clubs.infrastructure.seed import (
    seed_parliamentarians_clubs,
)

pytestmark = pytest.mark.anyio

ADMIN = DEV_USERS[0]  # TEST123, role admin — may write
MEMBER = DEV_USERS[1]  # MEMBER1, plain member — writes forbidden (no MANAGE_PARLIAMENTARIANS)


# --- domain unit: type invariant + expand/partition ------------------------


def test_club_type_invariant() -> None:
    Club(name="Klub", type="klub", color="#fff")  # allowed set → ok
    Club(name="Koło", type="koło", color="#fff")
    Club(name="Komitet", type="komitet", color="#fff")
    with pytest.raises(ValidationError):
        Club(name="Zły", type="stronnictwo", color="#fff")


def test_expand_sets_club_fields_or_null() -> None:
    club = Club(id=1, name="Klub Obywatelski", type="klub", color="#f59e0b")
    affiliated = expand(Parliamentarian(id=1, clubId=1), club)
    assert affiliated.clubName == "Klub Obywatelski" and affiliated.clubColor == "#f59e0b"
    unaffiliated = expand(Parliamentarian(id=2, clubId=None), None)
    assert unaffiliated.clubName is None and unaffiliated.clubColor is None


def test_partition_splits_and_expands() -> None:
    clubs = [Club(id=1, name="A", type="klub", color="#111")]
    people = [
        Parliamentarian(id=1, clubId=1),
        Parliamentarian(id=2, clubId=None),
        Parliamentarian(id=3, clubId=1),
    ]
    affiliated, unaffiliated = partition(people, clubs)
    assert [p.id for p in affiliated] == [1, 3]
    assert [p.id for p in unaffiliated] == [2]
    assert affiliated[0].clubName == "A" and affiliated[0].clubColor == "#111"


# --- API integration (checklist #1-#9) -------------------------------------


@pytest.fixture
async def seeded(async_session):
    """Seed users (for auth/RBAC) + the clubs/parliamentarians registry."""
    await seed_users(async_session)
    await seed_parliamentarians_clubs(async_session)
    await async_session.commit()


async def _bearer(client, user=ADMIN) -> dict[str, str]:
    resp = await client.post(
        "/api/auth/login",
        json={"username": user["username"], "password": user["password"]},
    )
    return {"Authorization": f"Bearer {resp.json()['token']}"}


async def test_list_partitions_affiliated_unaffiliated(client, seeded) -> None:  # #1
    resp = await client.get("/api/parliamentarians", headers=await _bearer(client))
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"parliamentarians", "unaffiliated"}
    assert all(p["clubId"] is not None for p in body["parliamentarians"])
    assert all(p["clubId"] is None for p in body["unaffiliated"])
    # affiliated carry expanded club fields; unaffiliated are null
    first = body["parliamentarians"][0]
    assert first["clubName"] == "Klub Obywatelski" and first["clubColor"] == "#f59e0b"
    assert {"firstName", "lastName", "functions", "commissions"} <= first.keys()
    assert body["unaffiliated"][0]["clubName"] is None
    # Bearer required
    assert (await client.get("/api/parliamentarians")).status_code == 401


async def test_post_creates_new(client, seeded) -> None:  # #2
    payload = {
        "firstName": "Nowy",
        "lastName": "Poseł",
        "clubId": 1,
        "functions": ["Wiceprzewodniczący"],
        "commissions": ["Komisja Kultury"],
    }
    resp = await client.post(
        "/api/parliamentarians", json=payload, headers=await _bearer(client)
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] is not None
    assert body["clubName"] == "Klub Obywatelski" and body["clubColor"] == "#f59e0b"
    assert body["functions"] == ["Wiceprzewodniczący"]
    # a genuinely new row (id beyond the 4 seeded)
    assert body["id"] > 4


async def test_post_upserts_existing(client, seeded) -> None:  # #3 (C7)
    headers = await _bearer(client)
    before = (await client.get("/api/parliamentarians", headers=headers)).json()
    total_before = len(before["parliamentarians"]) + len(before["unaffiliated"])
    # POST with an existing id → update in place, not a duplicate
    payload = {
        "id": 1,
        "firstName": "Anna",
        "lastName": "Kowalska-Nowak",
        "clubId": 2,
        "functions": [],
        "commissions": [],
    }
    resp = await client.post("/api/parliamentarians", json=payload, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == 1
    assert body["lastName"] == "Kowalska-Nowak"
    assert body["clubId"] == 2 and body["clubName"] == "Koło Niezależnych"
    after = (await client.get("/api/parliamentarians", headers=headers)).json()
    total_after = len(after["parliamentarians"]) + len(after["unaffiliated"])
    assert total_after == total_before  # no duplicate created


async def test_put_updates(client, seeded) -> None:  # #4
    headers = await _bearer(client)
    payload = {
        "firstName": "Piotr",
        "lastName": "Nowak-Zmieniony",
        "clubId": None,
        "functions": [],
        "commissions": [],
    }
    resp = await client.put("/api/parliamentarians/2", json=payload, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == 2 and body["lastName"] == "Nowak-Zmieniony"
    assert body["clubId"] is None and body["clubName"] is None
    # unknown id → 404
    missing = await client.put(
        "/api/parliamentarians/999", json=payload, headers=headers
    )
    assert missing.status_code == 404
    assert missing.json() == {"message": "Nie znaleziono parlamentarzysty"}


async def test_delete_unlinks(client, seeded) -> None:  # #5
    headers = await _bearer(client)
    resp = await client.delete("/api/parliamentarians/1", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"success": True}
    body = (await client.get("/api/parliamentarians", headers=headers)).json()
    ids = [p["id"] for p in body["parliamentarians"]] + [
        p["id"] for p in body["unaffiliated"]
    ]
    assert 1 not in ids  # gone from the registry entirely


async def test_clubs_bare_array(client, seeded) -> None:  # #6
    resp = await client.get("/api/clubs", headers=await _bearer(client))
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list) and len(body) == 2
    assert {"id", "name", "type", "color"} <= body[0].keys()
    assert body[0]["members"] == []
    assert (await client.get("/api/clubs")).status_code == 401


async def test_create_club(client, seeded) -> None:  # #7
    payload = {"name": "Komitet Młodych", "type": "komitet", "color": "#10b981"}
    resp = await client.post("/api/clubs", json=payload, headers=await _bearer(client))
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] is not None
    assert body["name"] == "Komitet Młodych" and body["type"] == "komitet"
    assert body["members"] == []


async def test_delete_club_unlinks_members(client, seeded) -> None:  # #8
    headers = await _bearer(client)
    resp = await client.delete("/api/clubs/1", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"success": True}
    body = (await client.get("/api/parliamentarians", headers=headers)).json()
    # former members of club 1 now appear as unaffiliated with null club fields
    unaffiliated_ids = {p["id"] for p in body["unaffiliated"]}
    assert {1, 2} <= unaffiliated_ids
    for p in body["unaffiliated"]:
        if p["id"] in {1, 2}:
            assert p["clubId"] is None and p["clubName"] is None
    # club is gone
    clubs = (await client.get("/api/clubs", headers=headers)).json()
    assert 1 not in {c["id"] for c in clubs}


async def test_writes_require_manage_parliamentarians(client, seeded) -> None:  # #9
    member_headers = await _bearer(client, MEMBER)
    admin_headers = await _bearer(client, ADMIN)
    payload = {"firstName": "X", "lastName": "Y", "clubId": None}
    club_payload = {"name": "K", "type": "klub", "color": "#000"}

    # member (no MANAGE_PARLIAMENTARIANS) → 403 on every write
    assert (
        await client.post("/api/parliamentarians", json=payload, headers=member_headers)
    ).status_code == 403
    assert (
        await client.put(
            "/api/parliamentarians/1", json=payload, headers=member_headers
        )
    ).status_code == 403
    assert (
        await client.delete("/api/parliamentarians/1", headers=member_headers)
    ).status_code == 403
    assert (
        await client.post("/api/clubs", json=club_payload, headers=member_headers)
    ).status_code == 403
    assert (
        await client.delete("/api/clubs/1", headers=member_headers)
    ).status_code == 403
    assert (await client.post("/api/parliamentarians", json=payload)).status_code == 401

    # admin → allowed
    ok = await client.post("/api/clubs", json=club_payload, headers=admin_headers)
    assert ok.status_code == 201
