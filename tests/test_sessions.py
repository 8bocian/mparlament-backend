"""Slice 04 — sessions (posiedzenia): current session, session list, speakers.

Shapes come verbatim from BACKEND_SPEC.md §4 (#4-#7, #39/#40), §2 (Session, CurrentSession,
Speaker) + CONVENTIONS C3 (admin/marshal on writes), C6 (both current-session aliases return the
same superset object), C10 (bare arrays for #7/#39), C13 (FE date formats kept verbatim).

Layering (CLAUDE.md): domain unit → API integration. The domain tests exercise the partial-merge
invariant and the schedule-status value-object guard directly; the API tests mirror the doc's
TDD checklist #1-#7.
"""

from __future__ import annotations

import pytest

from mparlament.slices.auth_identity.infrastructure.seed import DEV_USERS, seed_users
from mparlament.slices.sessions.domain.entities import (
    AgendaPoint,
    CurrentSession,
    ScheduleItem,
)
from mparlament.slices.sessions.infrastructure.seed import seed_sessions

pytestmark = pytest.mark.anyio

ADMIN = DEV_USERS[0]  # TEST123, role=admin
MEMBER = DEV_USERS[1]  # MEMBER1, role=member (no MANAGE_*)


# --- domain unit -----------------------------------------------------------


def test_schedule_item_rejects_unknown_status() -> None:
    with pytest.raises(ValueError):
        ScheduleItem(time="10:00", title="Otwarcie", status="bogus")


def test_current_session_partial_merge_leaves_other_fields() -> None:
    """with_patch overwrites only provided keys (spec #5 partial PUT)."""
    base = CurrentSession(
        id=1,
        title="Posiedzenie",
        status="TRWA",
        active=True,
        zoContent="stare ZO",
        schedule=[ScheduleItem(time="10:00", title="Otwarcie", status="done")],
    )
    merged = base.with_patch(
        {"schedule": [{"time": "11:00", "title": "Debata", "status": "active"}]}
    )
    assert [s.title for s in merged.schedule] == ["Debata"]
    assert merged.zoContent == "stare ZO"  # untouched
    assert merged.status == "TRWA"


def test_current_session_partial_merge_point_and_zo() -> None:
    base = CurrentSession(id=1, title="P", status="TRWA", zoContent="old")
    merged = base.with_patch(
        {
            "currentPoint": {"number": "2", "title": "Punkt 2", "type": "voting"},
            "zoContent": "new ZO",
        }
    )
    assert isinstance(merged.currentPoint, AgendaPoint)
    assert merged.currentPoint.title == "Punkt 2"
    assert merged.zoContent == "new ZO"


# --- API integration -------------------------------------------------------


@pytest.fixture
async def seeded(async_session):
    """Seed users + the sessions slice into the shared in-memory DB."""
    await seed_users(async_session)
    await seed_sessions(async_session)
    await async_session.commit()


async def _bearer(client, user=ADMIN) -> dict[str, str]:
    resp = await client.post(
        "/api/auth/login",
        json={"username": user["username"], "password": user["password"]},
    )
    return {"Authorization": f"Bearer {resp.json()['token']}"}


SUPERSET_KEYS = {
    "id",
    "title",
    "status",
    "active",
    "date",
    "start",
    "startTime",
    "end",
    "endTime",
    "currentSpeaker",
    "currentPoint",
    "schedule",
    "zoContent",
}


async def test_get_current_session_superset(client, seeded) -> None:  # checklist #1
    resp = await client.get("/api/session/current", headers=await _bearer(client))
    assert resp.status_code == 200
    body = resp.json()
    assert SUPERSET_KEYS <= body.keys()
    assert isinstance(body["schedule"], list) and body["schedule"]
    for item in body["schedule"]:
        assert {"time", "title", "status"} <= item.keys()


async def test_get_current_session_requires_auth(client, seeded) -> None:
    resp = await client.get("/api/session/current")
    assert resp.status_code == 401
    assert resp.json() == {"message": "Wymagane uwierzytelnienie"}


async def test_sessions_current_alias_identical(client, seeded) -> None:  # checklist #2
    headers = await _bearer(client)
    a = await client.get("/api/session/current", headers=headers)
    b = await client.get("/api/sessions/current", headers=headers)
    assert a.status_code == b.status_code == 200
    assert a.json() == b.json()


async def test_put_session_partial_schedule(client, seeded) -> None:  # checklist #3
    headers = await _bearer(client)
    before = (await client.get("/api/session/current", headers=headers)).json()
    new_schedule = [
        {"time": "12:00", "title": "Nowy punkt", "status": "active"},
        {"time": "13:00", "title": "Przerwa", "status": "waiting"},
    ]
    resp = await client.put(
        "/api/session/current", headers=headers, json={"schedule": new_schedule}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert [s["title"] for s in body["schedule"]] == ["Nowy punkt", "Przerwa"]
    assert body["zoContent"] == before["zoContent"]  # unchanged
    assert SUPERSET_KEYS <= body.keys()  # full object returned


async def test_put_session_partial_point_and_zo(client, seeded) -> None:  # checklist #4
    headers = await _bearer(client)
    before = (await client.get("/api/session/current", headers=headers)).json()
    resp = await client.put(
        "/api/session/current",
        headers=headers,
        json={
            "currentPoint": {"number": "5", "title": "Głosowanie", "type": "voting"},
            "zoContent": "Zmieniona treść ZO",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["currentPoint"]["title"] == "Głosowanie"
    assert body["zoContent"] == "Zmieniona treść ZO"
    # schedule left intact
    assert body["schedule"] == before["schedule"]


async def test_put_session_requires_admin_or_marshal(client, seeded) -> None:  # #5
    headers = await _bearer(client, MEMBER)
    resp = await client.put(
        "/api/session/current", headers=headers, json={"zoContent": "x"}
    )
    assert resp.status_code == 403
    assert resp.json() == {"message": "Brak uprawnień"}


async def test_list_sessions_shape(client, seeded) -> None:  # checklist #6
    resp = await client.get("/api/sessions")  # public (no auth)
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list) and body  # bare array (C10)
    for item in body:
        assert {"id", "name", "date", "city"} <= item.keys()


async def test_speakers_get_and_post(client, seeded) -> None:  # checklist #7
    headers = await _bearer(client)
    # GET (Bearer) → bare array of {name, club, role}
    listing = await client.get("/api/speakers", headers=headers)
    assert listing.status_code == 200
    assert isinstance(listing.json(), list)
    before = len(listing.json())

    # POST (admin/marshal) → {id, name, club, role}
    created = await client.post(
        "/api/speakers",
        headers=headers,
        json={"name": "Nowy Mówca", "club": "KO", "role": "Poseł"},
    )
    assert created.status_code == 201
    payload = created.json()
    assert {"id", "name", "club", "role"} <= payload.keys()
    assert payload["name"] == "Nowy Mówca"

    # subsequent GET includes it
    after = await client.get("/api/speakers", headers=headers)
    assert len(after.json()) == before + 1
    assert any(s["name"] == "Nowy Mówca" for s in after.json())


async def test_post_speaker_requires_admin_or_marshal(client, seeded) -> None:
    headers = await _bearer(client, MEMBER)
    resp = await client.post(
        "/api/speakers",
        headers=headers,
        json={"name": "X", "club": "Y", "role": "Z"},
    )
    assert resp.status_code == 403
    assert resp.json() == {"message": "Brak uprawnień"}


async def test_speakers_requires_auth(client, seeded) -> None:
    resp = await client.get("/api/speakers")
    assert resp.status_code == 401
    assert resp.json() == {"message": "Wymagane uwierzytelnienie"}
