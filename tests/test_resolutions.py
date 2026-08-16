"""Slice 06 — resolutions (uchwały): documents, docx upload, signatures, slug/id polymorphism.

Shapes come verbatim from BACKEND_SPEC.md §4 (#17-#22), §2 (Resolution, ResolutionSignature) +
CONVENTIONS C2 (optional/identity-chain auth), C5 (slug-or-id), C10 (wrappers), C11 (Polish
messages), C12 (slug gen), C13 (createdAt date / signature ISO), C14 (docx storage + filePath).

Layering (CLAUDE.md): domain unit (slugify) → API integration mirroring the doc's TDD checklist.
"""

from __future__ import annotations

import json
import re

import pytest

from mparlament.slices.auth_identity.infrastructure.seed import DEV_USERS, seed_users
from mparlament.slices.resolutions.domain.entities import slugify
from mparlament.slices.resolutions.infrastructure.seed import seed_resolutions
from mparlament.slices.sessions.infrastructure.seed import seed_sessions

pytestmark = pytest.mark.anyio

ADMIN = DEV_USERS[0]  # TEST123, user id 1 — author of resolution 1
MEMBER = DEV_USERS[1]  # MEMBER1, user id 2 — not the author of resolution 1
MANAGER = DEV_USERS[2]  # MEMBER2, user id 3


# --- domain unit: slugify (checklist #1, C12) ------------------------------


def test_slugify_polish_lowercase_and_spaces() -> None:
    assert slugify("Uchwała klimatyczna") == "uchwała-klimatyczna"
    assert slugify("  Hello World!  ") == "hello-world"


def test_slugify_collision_appends_suffix() -> None:
    assert slugify("Test", {"test"}) == "test-2"
    assert slugify("Test", {"test", "test-2"}) == "test-3"


# --- API integration (checklist #2-12) -------------------------------------


@pytest.fixture
async def seeded(async_session):
    """Seed users + sessions + resolutions (with author auto-signatures) into the shared DB."""
    await seed_users(async_session)
    await seed_sessions(async_session)
    await seed_resolutions(async_session)
    await async_session.commit()


async def _bearer(client, user=ADMIN) -> dict[str, str]:
    resp = await client.post(
        "/api/auth/login",
        json={"username": user["username"], "password": user["password"]},
    )
    return {"Authorization": f"Bearer {resp.json()['token']}"}


async def test_list_resolutions_wrapper(client, seeded) -> None:  # #2
    resp = await client.get("/api/resolutions")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["resolutions"], list) and body["resolutions"]
    first = body["resolutions"][0]
    assert "chapters" in first and "slug" in first and "signatures" in first


async def test_get_by_slug_shape(client, seeded) -> None:  # #3
    resp = await client.get("/api/resolutions/uchwala-w-sprawie-polityki-klimatycznej")
    assert resp.status_code == 200
    body = resp.json()
    assert {"resolution", "signedUsers", "session"} <= body.keys()
    assert isinstance(body["resolution"]["chapters"], list)
    assert body["session"] == {"city": "Warszawa", "date": "19.09.2026"}
    # author auto-signature is present in signedUsers (type="author").
    assert any(s["type"] == "author" for s in body["signedUsers"])


async def test_get_by_numeric_id_polymorphic(client, seeded) -> None:  # #4 (VotingPage #18b)
    resp = await client.get("/api/resolutions/1", headers=await _bearer(client))
    assert resp.status_code == 200
    body = resp.json()
    assert body["resolution"]["id"] == 1
    assert body["resolution"]["slug"] == "uchwala-w-sprawie-polityki-klimatycznej"


async def test_get_404(client, seeded) -> None:  # #5
    resp = await client.get("/api/resolutions/nie-istnieje")
    assert resp.status_code == 404
    assert resp.json() == {"message": "Nie znaleziono uchwały"}


async def test_current_user_block_present_when_authed(client, seeded) -> None:  # #6
    headers = await _bearer(client, MEMBER)
    authed = (await client.get("/api/resolutions/1", headers=headers)).json()
    assert set(authed["currentUser"].keys()) == {
        "hasSigned",
        "isAuthor",
        "signatureType",
        "isAutoSigned",
    }
    assert authed["currentUser"]["hasSigned"] is False
    assert authed["currentUser"]["isAuthor"] is False
    # Anonymous → no currentUser key.
    anon = (await client.get("/api/resolutions/1")).json()
    assert "currentUser" not in anon


async def test_current_user_block_flags_author(client, seeded) -> None:
    # The author (user 1) is auto-signed → isAuthor + isAutoSigned true, signatureType "author".
    headers = await _bearer(client, ADMIN)
    body = (await client.get("/api/resolutions/1", headers=headers)).json()
    cu = body["currentUser"]
    assert cu["isAuthor"] is True
    assert cu["hasSigned"] is True
    assert cu["signatureType"] == "author"
    assert cu["isAutoSigned"] is True


async def test_create_multipart(client, seeded, tmp_path, monkeypatch) -> None:  # #7
    # Redirect uploads to a temp dir so the test never writes into the repo.
    from mparlament.shared.storage import LocalDiskStorage
    from mparlament.slices.resolutions.api import router as res_router

    monkeypatch.setattr(
        res_router._create, "_storage", LocalDiskStorage(base_dir=tmp_path)
    )

    data = {
        "title": "Uchwała testowa o transporcie",
        "fileName": "uchwala-transport.docx",
        "author": "Piotr Wiśniewski",
        "authorId": 3,
        "party": "PiS",
        "sessionId": 1,
        "preamble": "Preambuła.",
        "chapters": [
            {
                "id": 1,
                "title": "Rozdział I",
                "articles": [{"id": 1, "number": "1", "content": "Treść."}],
            }
        ],
    }
    resp = await client.post(
        "/api/resolutions",
        files={"file": ("uchwala-transport.docx", b"PK\x03\x04 fake docx", "application/octet-stream")},
        data={"data": json.dumps(data)},
    )
    assert resp.status_code == 201
    created = resp.json()
    assert created["slug"] == "uchwała-testowa-o-transporcie"
    assert created["status"] == "pending"
    assert created["signatures"] == 1
    assert re.match(r"^\d{4}-\d{2}-\d{2}$", created["createdAt"])
    assert created["filePath"] == "/uploads/resolutions/uchwala-transport.docx"
    # File actually landed on disk.
    assert (tmp_path / "resolutions" / "uchwala-transport.docx").exists()
    # Author auto-signature exists (type="author").
    detail = (await client.get(f"/api/resolutions/{created['slug']}")).json()
    assert any(s["type"] == "author" for s in detail["signedUsers"])


async def test_sign_and_refresh(client, seeded) -> None:  # #8
    headers = await _bearer(client, MEMBER)
    before = (await client.get("/api/resolutions/1", headers=headers)).json()
    resp = await client.post("/api/resolutions/1/sign", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"success": True}
    after = (await client.get("/api/resolutions/1", headers=headers)).json()
    assert after["currentUser"]["hasSigned"] is True
    assert after["resolution"]["signatures"] == before["resolution"]["signatures"] + 1
    assert any(
        s["type"] == "signature" and s["name"] == "Anna Nowak"
        for s in after["signedUsers"]
    )


async def test_sign_twice_conflict(client, seeded) -> None:  # #9
    headers = await _bearer(client, MEMBER)
    first = await client.post("/api/resolutions/1/sign", headers=headers)
    assert first.status_code == 200
    second = await client.post("/api/resolutions/1/sign", headers=headers)
    assert second.status_code == 400
    assert second.json() == {"message": "Już podpisałeś tę uchwałę"}


async def test_unsign_author_forbidden(client, seeded) -> None:  # #10
    # The author (ADMIN, user 1) cannot remove their auto-signature on resolution 1.
    headers = await _bearer(client, ADMIN)
    resp = await client.delete("/api/resolutions/1/sign", headers=headers)
    assert resp.status_code == 403
    assert resp.json() == {"message": "Autor nie może usunąć podpisu"}


async def test_unsign_member_ok(client, seeded) -> None:  # #11
    headers = await _bearer(client, MEMBER)
    await client.post("/api/resolutions/1/sign", headers=headers)
    resp = await client.delete("/api/resolutions/1/sign", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"success": True, "message": "Podpis został usunięty"}
    after = (await client.get("/api/resolutions/1", headers=headers)).json()
    assert after["currentUser"]["hasSigned"] is False


async def test_session_resolutions_shape(client, seeded) -> None:  # #12
    resp = await client.get("/api/resolutions/session/1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["sessionId"] == 1
    assert body["count"] == len(body["resolutions"])
    assert body["count"] >= 2
