"""Slice 07 — amendments (poprawki): list/detail/create/withdraw + article changes.

Shapes come verbatim from BACKEND_SPEC.md §4 (#23-#28), §2 (Amendment) + CONVENTIONS C2
(identity chain for withdraw), C5 (slug-or-id parent), C10 (wrappers incl. bare array + {data}),
C11 (Polish messages), C13 (createdAt date).

Layering (CLAUDE.md): domain unit (withdraw, Change conventions) → API integration mirroring the
doc's TDD checklist.
"""

from __future__ import annotations

import re

import pytest

from mparlament.shared.domain import ConflictError, PermissionDeniedError
from mparlament.slices.amendments.domain.entities import Amendment, Change
from mparlament.slices.amendments.infrastructure.seed import seed_amendments
from mparlament.slices.auth_identity.infrastructure.seed import DEV_USERS, seed_users
from mparlament.slices.resolutions.infrastructure.seed import seed_resolutions
from mparlament.slices.sessions.infrastructure.seed import seed_sessions

pytestmark = pytest.mark.anyio

ADMIN = DEV_USERS[0]  # TEST123, user id 1 — NOT the author of amendment 1
MEMBER = DEV_USERS[1]  # MEMBER1, user id 2 — Anna Nowak, author of amendment 1
MANAGER = DEV_USERS[2]  # MEMBER2, user id 3 — Piotr Wiśniewski, author of amendment 2

RES_SLUG = "uchwala-w-sprawie-polityki-klimatycznej"


# --- domain unit: withdraw + Change conventions (checklist #9-12, §2) -------


def test_withdraw_author_only_and_default_reason() -> None:
    amendment = Amendment(id=1, resolutionId=1, authorId=2, status="pending")
    amendment.withdraw(actor_id=2, reason=None)
    assert amendment.status == "withdrawn"
    assert amendment.withdrawnReason == "Brak podanego powodu"


def test_withdraw_rejects_non_author() -> None:
    amendment = Amendment(id=1, resolutionId=1, authorId=2, status="pending")
    with pytest.raises(PermissionDeniedError):
        amendment.withdraw(actor_id=99, reason="nie mój")


def test_withdraw_twice_conflicts() -> None:
    amendment = Amendment(id=1, resolutionId=1, authorId=2, status="pending")
    amendment.withdraw(actor_id=2, reason="powód")
    with pytest.raises(ConflictError):
        amendment.withdraw(actor_id=2, reason="znowu")


def test_change_conventions_add_and_delete() -> None:
    add = Change(articleId="new_123", type="add", before="", after="Nowy artykuł.")
    delete = Change(articleId=3, type="delete", before="Stary.", after="")
    assert add.before == "" and add.type == "add"
    assert delete.after == "" and delete.type == "delete"


# --- API integration (checklist #1-12) -------------------------------------


@pytest.fixture
async def seeded(async_session):
    """Seed users + sessions + resolutions + amendments into the shared DB."""
    await seed_users(async_session)
    await seed_sessions(async_session)
    await seed_resolutions(async_session)
    await seed_amendments(async_session)
    await async_session.commit()


async def _bearer(client, user=MEMBER) -> dict[str, str]:
    resp = await client.post(
        "/api/auth/login",
        json={"username": user["username"], "password": user["password"]},
    )
    return {"Authorization": f"Bearer {resp.json()['token']}"}


async def test_list_amendments_by_slug(client, seeded) -> None:  # #1
    resp = await client.get(f"/api/resolutions/{RES_SLUG}/amendments")
    assert resp.status_code == 200
    body = resp.json()
    assert {"resolution", "session", "amendments"} <= body.keys()
    assert body["resolution"] == {"title": "Uchwała w sprawie polityki klimatycznej", "slug": RES_SLUG}
    assert body["session"] == {"city": "Warszawa", "date": "19.09.2026"}
    assert isinstance(body["amendments"], list) and len(body["amendments"]) == 2
    assert body["amendments"][0]["changes"]  # changes carried through


async def test_list_amendments_by_id_polymorphic(client, seeded) -> None:  # #2 (C5)
    by_id = (await client.get("/api/resolutions/1/amendments")).json()
    by_slug = (await client.get(f"/api/resolutions/{RES_SLUG}/amendments")).json()
    assert by_id == by_slug


async def test_create_amendment(client, seeded) -> None:  # #3
    payload = {
        "resolutionId": 999,  # server overrides with the resolved parent's id
        "author": "Anna Nowak",
        "authorId": 2,
        "club": "KO",
        "content": "Nowa poprawka.",
        "status": "pending",
        "changes": [
            {"articleId": 2, "type": "modify", "before": "Definicje.", "after": "Rozszerzone definicje."}
        ],
        "withdrawnReason": None,
    }
    resp = await client.post(f"/api/resolutions/{RES_SLUG}/amendments", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    amendment = body["amendment"]
    assert amendment["id"] is not None
    assert amendment["resolutionId"] == 1  # overridden from the parent, not 999
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", amendment["createdAt"])
    assert amendment["status"] == "pending"
    assert amendment["changes"] == [
        {"articleId": 2, "type": "modify", "before": "Definicje.", "after": "Rozszerzone definicje."}
    ]


async def test_create_amendment_add_and_delete_conventions(client, seeded) -> None:  # #4
    payload = {
        "author": "Anna Nowak",
        "authorId": 2,
        "club": "KO",
        "content": "Dodanie i usunięcie.",
        "status": "pending",
        "changes": [
            {"articleId": "new_1720000000000", "type": "add", "before": "", "after": "Nowy artykuł."},
            {"articleId": 3, "type": "delete", "before": "Harmonogram.", "after": ""},
        ],
    }
    resp = await client.post(f"/api/resolutions/{RES_SLUG}/amendments", json=payload)
    assert resp.status_code == 201
    changes = resp.json()["amendment"]["changes"]
    assert changes[0] == {
        "articleId": "new_1720000000000",
        "type": "add",
        "before": "",
        "after": "Nowy artykuł.",
    }
    assert changes[1] == {"articleId": 3, "type": "delete", "before": "Harmonogram.", "after": ""}


async def test_create_404_missing_resolution(client, seeded) -> None:  # #5
    resp = await client.post(
        "/api/resolutions/nie-istnieje/amendments",
        json={"author": "X", "authorId": 2, "content": "y", "changes": []},
    )
    assert resp.status_code == 404
    assert resp.json() == {"message": "Nie znaleziono uchwały"}


async def test_get_amendment_under_resolution(client, seeded) -> None:  # #6
    resp = await client.get(f"/api/resolutions/{RES_SLUG}/amendments/1")
    assert resp.status_code == 200
    body = resp.json()
    assert {"resolution", "amendment", "session"} <= body.keys()
    assert body["resolution"] == {"title": "Uchwała w sprawie polityki klimatycznej", "slug": RES_SLUG}
    assert body["amendment"]["id"] == 1
    assert body["session"] == {"city": "Warszawa", "date": "19.09.2026"}
    # unknown amendment under a valid resolution → 404 Nie znaleziono poprawki
    missing = await client.get(f"/api/resolutions/{RES_SLUG}/amendments/999")
    assert missing.status_code == 404
    assert missing.json() == {"message": "Nie znaleziono poprawki"}


async def test_list_amendments_bare_array(client, seeded) -> None:  # #7
    resp = await client.get("/api/amendments", headers=await _bearer(client))
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list) and len(body) == 2
    assert {"id", "resolutionId", "changes", "status"} <= body[0].keys()
    # Bearer required.
    assert (await client.get("/api/amendments")).status_code == 401


async def test_get_amendment_wrapped_in_data(client, seeded) -> None:  # #8
    resp = await client.get("/api/amendments/1", headers=await _bearer(client))
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"data"}
    assert body["data"]["id"] == 1
    assert body["data"]["resolution"] == {
        "id": 1,
        "title": "Uchwała w sprawie polityki klimatycznej",
        "slug": RES_SLUG,
    }
    # 404 for a missing amendment.
    missing = await client.get("/api/amendments/999", headers=await _bearer(client))
    assert missing.status_code == 404
    assert missing.json() == {"message": "Nie znaleziono poprawki"}


async def test_withdraw_by_author(client, seeded) -> None:  # #9
    headers = await _bearer(client, MEMBER)  # Anna Nowak, author of amendment 1
    resp = await client.post(
        "/api/amendments/1/withdraw", json={"reason": "Wycofuję po konsultacjach."}, headers=headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["amendment"]["status"] == "withdrawn"
    assert body["amendment"]["withdrawnReason"] == "Wycofuję po konsultacjach."


async def test_withdraw_not_author_403(client, seeded) -> None:  # #10
    headers = await _bearer(client, ADMIN)  # Jan Kowalski, NOT the author of amendment 1
    resp = await client.post("/api/amendments/1/withdraw", json={"reason": "x"}, headers=headers)
    assert resp.status_code == 403
    assert resp.json() == {"message": "Brak uprawnień"}


async def test_withdraw_already_withdrawn_400(client, seeded) -> None:  # #11
    headers = await _bearer(client, MEMBER)
    first = await client.post("/api/amendments/1/withdraw", json={"reason": "raz"}, headers=headers)
    assert first.status_code == 200
    second = await client.post("/api/amendments/1/withdraw", json={"reason": "dwa"}, headers=headers)
    assert second.status_code == 400


async def test_withdraw_default_reason(client, seeded) -> None:  # #12
    headers = await _bearer(client, MEMBER)
    resp = await client.post("/api/amendments/1/withdraw", json={}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["amendment"]["withdrawnReason"] == "Brak podanego powodu"


# --- cascade adapter: votings #14 flips amendment status (DoD) --------------


async def test_linked_item_status_updater_flips_amendment(async_session) -> None:
    """The votings archive (#14) cascade can flip an amendment's status by id (loose coupling)."""
    from mparlament.slices.amendments.infrastructure.repository import (
        AmendmentLinkedItemStatusUpdater,
        SqlAlchemyAmendmentRepository,
    )

    await seed_users(async_session)
    await seed_sessions(async_session)
    await seed_resolutions(async_session)
    await seed_amendments(async_session)
    await async_session.commit()

    updater = AmendmentLinkedItemStatusUpdater()
    await updater.update_status(async_session, "amendment", "1", "accepted")
    await updater.update_status(async_session, "resolution", "1", "rejected")  # ignored
    await async_session.commit()

    repo = SqlAlchemyAmendmentRepository()
    assert (await repo.get_by_id(async_session, 1)).status == "accepted"
