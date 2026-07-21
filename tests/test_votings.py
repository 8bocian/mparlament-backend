"""Slice 05 — votings (głosowania): lifecycle, cast votes, computed live stats, attachments.

Shapes come verbatim from BACKEND_SPEC.md §4 (#8-#16), §2 (Voting, Vote) + CONVENTIONS C3
(MANAGE_VOTINGS + managers), C4 (abstain normalize), C8 (recipients incl. individual→members),
C10 (bare array #8, computed shapes), C13 (time strings), C15 (authoritative status).

Layering (CLAUDE.md): domain unit → application use-case → API integration. The domain tests
exercise ``normalize_vote`` and eligibility directly; the application tests cover the archive
linked-item cascade with a fake updater (the resolutions slice is not built yet — loose coupling
by id, README); the API tests mirror the doc's TDD checklist.
"""

from __future__ import annotations

import pytest

from mparlament.shared.domain import ValidationError
from mparlament.slices.auth_identity.infrastructure.seed import DEV_USERS, seed_users
from mparlament.slices.votings.application.use_cases import ArchiveVotingUseCase
from mparlament.slices.votings.domain.entities import (
    DirectoryUser,
    Voting,
    Vote,
    normalize_vote,
)
from mparlament.slices.votings.infrastructure.seed import seed_votings

pytestmark = pytest.mark.anyio

ADMIN = DEV_USERS[0]  # TEST123, role=admin
MEMBER = DEV_USERS[1]  # MEMBER1, role=member (no MANAGE_*), group="A"
MANAGER = DEV_USERS[2]  # MEMBER2, MANAGE_VOTINGS, group="B"


# --- domain unit: normalize_vote (checklist #1) ----------------------------


def test_normalize_vote_maps_abstain() -> None:
    assert normalize_vote("abstain") == "abstained"
    assert normalize_vote("abstained") == "abstained"
    assert normalize_vote("for") == "for"
    assert normalize_vote("against") == "against"


def test_normalize_vote_rejects_invalid() -> None:
    with pytest.raises(ValidationError):
        normalize_vote("maybe")


# --- domain unit: eligibility (checklist #2-4, C8) -------------------------

_USERS = [
    DirectoryUser(id=1, name="Admin", club="TEST", group=None),
    DirectoryUser(id=2, name="Anna", club="KO", group="A"),
    DirectoryUser(id=3, name="Piotr", club="PiS", group="B"),
]


def test_eligibility_all() -> None:  # checklist #2
    voting = Voting(id=1, title="V", recipientsType="all")
    assert {u.id for u in voting.eligible_users(_USERS)} == {1, 2, 3}


def test_eligibility_members_and_individual() -> None:  # checklist #3
    members = Voting(id=1, title="V", recipientsType="members", selectedMembers=[2, 3])
    assert {u.id for u in members.eligible_users(_USERS)} == {2, 3}
    # "individual" normalizes to "members" on construction (C8) and resolves identically.
    individual = Voting(
        id=1, title="V", recipientsType="individual", selectedMembers=[2, 3]
    )
    assert individual.recipientsType == "members"
    assert {u.id for u in individual.eligible_users(_USERS)} == {2, 3}


def test_eligibility_groups() -> None:  # checklist #4
    voting = Voting(id=1, title="V", recipientsType="groups", selectedGroups=["A"])
    assert {u.id for u in voting.eligible_users(_USERS)} == {2}


# --- application unit: archive linked-item cascade (checklist #14) ----------
#
# The resolutions slice (doc 06) is not built yet, so the cascade is verified against a fake
# ``LinkedItemStatusUpdater`` (loose coupling by id, README) rather than a real resolution row.


class _FakeVotingRepo:
    def __init__(self, voting: Voting) -> None:
        self._voting = voting

    async def get(self, session, voting_id):
        return self._voting if voting_id == self._voting.id else None

    async def update(self, session, voting):
        self._voting = voting
        return voting

    async def list_all(self, session):
        return [self._voting]

    async def add(self, session, voting):
        return voting

    async def delete(self, session, voting_id):
        return None


class _FakeVoteRepo:
    def __init__(self, votes: list[Vote]) -> None:
        self._votes = votes

    async def list_by_voting(self, session, voting_id):
        return [v for v in self._votes if v.votingId == voting_id]

    async def get_user_vote(self, session, voting_id, user_id):
        return None

    async def add(self, session, vote):
        self._votes.append(vote)
        return vote


class _FakeDirectory:
    async def list_all(self, session):
        return []


class _SpyLinkedUpdater:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def update_status(self, session, item_type, item_id, status):
        self.calls.append((item_type, item_id, status))


async def _run_archive(votes: list[Vote]):
    voting = Voting(id=7, title="V", linkedItemType="resolution", linkedItemId="42")
    spy = _SpyLinkedUpdater()
    use_case = ArchiveVotingUseCase(
        _FakeVotingRepo(voting), _FakeVoteRepo(votes), _FakeDirectory(), spy
    )
    result = await use_case.execute(session=None, voting_id=7, requester_id=1)
    return voting, spy, result


async def test_archive_cascades_accepted_when_for_wins() -> None:  # checklist #14a
    votes = [
        Vote(votingId=7, userId=1, value="for"),
        Vote(votingId=7, userId=2, value="for"),
        Vote(votingId=7, userId=3, value="against"),
    ]
    voting, spy, result = await _run_archive(votes)
    assert voting.status == "archived"
    assert result["success"] is True
    assert spy.calls == [("resolution", "42", "accepted")]


async def test_archive_cascades_rejected_when_against_wins() -> None:  # checklist #14b
    votes = [
        Vote(votingId=7, userId=1, value="against"),
        Vote(votingId=7, userId=2, value="against"),
        Vote(votingId=7, userId=3, value="for"),
    ]
    _voting, spy, _result = await _run_archive(votes)
    assert spy.calls == [("resolution", "42", "rejected")]


# --- API integration (checklist #5-16) -------------------------------------


@pytest.fixture
async def seeded(async_session):
    """Seed users + votings into the shared in-memory DB."""
    await seed_users(async_session)
    await seed_votings(async_session)
    await async_session.commit()


async def _bearer(client, user=ADMIN) -> dict[str, str]:
    resp = await client.post(
        "/api/auth/login",
        json={"username": user["username"], "password": user["password"]},
    )
    return {"Authorization": f"Bearer {resp.json()['token']}"}


async def _me_id(client, headers) -> int:
    resp = await client.get("/api/auth/me", headers=headers)
    return resp.json()["id"]


COMPUTED_KEYS = {
    "votesFor",
    "votesAgainst",
    "abstained",
    "votedCount",
    "hasVoted",
    "myVote",
}


async def test_list_votings_is_array_with_computed(client, seeded) -> None:  # #5
    resp = await client.get("/api/votings", headers=await _bearer(client))
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list) and body  # bare array (C10)
    for item in body:
        assert COMPUTED_KEYS <= item.keys()


async def test_list_votings_requires_auth(client, seeded) -> None:
    resp = await client.get("/api/votings")
    assert resp.status_code == 401
    assert resp.json() == {"message": "Wymagane uwierzytelnienie"}


async def test_get_voting_detail_lists(client, seeded) -> None:  # #6
    resp = await client.get("/api/votings/1", headers=await _bearer(client))
    assert resp.status_code == 200
    body = resp.json()
    for key in ("eligibleUsers", "votedUsers", "notVotedUsers"):
        assert key in body
        for person in body[key]:
            assert set(person.keys()) == {"id", "name", "club"}
    assert body["totalEligible"] == len(body["eligibleUsers"])


async def test_get_voting_404(client, seeded) -> None:  # #7
    resp = await client.get("/api/votings/999", headers=await _bearer(client))
    assert resp.status_code == 404
    assert resp.json() == {"message": "Nie znaleziono głosowania"}


async def test_cast_vote_sets_myvote(client, seeded) -> None:  # #8
    headers = await _bearer(client, MEMBER)
    before = (await client.get("/api/votings/1", headers=headers)).json()
    resp = await client.post("/api/votings/1/vote", headers=headers, json={"vote": "for"})
    assert resp.status_code == 200
    assert resp.json()["vote"] == "for"
    after = (await client.get("/api/votings/1", headers=headers)).json()
    assert after["hasVoted"] is True
    assert after["myVote"] == "for"
    assert after["votesFor"] == before["votesFor"] + 1


async def test_cast_vote_twice_conflict(client, seeded) -> None:  # #9
    headers = await _bearer(client, MEMBER)
    first = await client.post("/api/votings/1/vote", headers=headers, json={"vote": "for"})
    assert first.status_code == 200
    second = await client.post(
        "/api/votings/1/vote", headers=headers, json={"vote": "against"}
    )
    assert second.status_code == 400
    assert second.json() == {"message": "Użytkownik już oddał głos"}


async def test_cast_abstain_counts_as_abstained(client, seeded) -> None:  # #10
    headers = await _bearer(client, MEMBER)
    resp = await client.post(
        "/api/votings/1/vote", headers=headers, json={"vote": "abstain"}
    )
    assert resp.status_code == 200
    assert resp.json()["vote"] == "abstained"  # normalized (C4)
    after = (await client.get("/api/votings/1", headers=headers)).json()
    assert after["abstained"] == 1


async def test_create_requires_manage_votings(client, seeded) -> None:  # #11
    body = {
        "title": "Nowe głosowanie",
        "category": "law",
        "recipientsType": "all",
        "startTime": "2026-09-19T15:00",
    }
    # member (no MANAGE_VOTINGS) → 403
    denied = await client.post(
        "/api/votings", headers=await _bearer(client, MEMBER), json=body
    )
    assert denied.status_code == 403
    assert denied.json() == {"message": "Brak uprawnień"}
    # admin → 201 with id
    created = await client.post(
        "/api/votings", headers=await _bearer(client, ADMIN), json=body
    )
    assert created.status_code == 201
    assert isinstance(created.json()["id"], int)


async def test_manager_can_edit(client, seeded) -> None:  # #12
    admin_headers = await _bearer(client, ADMIN)
    member_headers = await _bearer(client, MEMBER)
    member_id = await _me_id(client, member_headers)

    # Admin creates a voting managed by the plain member (who lacks MANAGE_VOTINGS).
    created = await client.post(
        "/api/votings",
        headers=admin_headers,
        json={"title": "Zarządzane", "recipientsType": "all", "managers": [member_id]},
    )
    voting_id = created.json()["id"]

    # The manager can PUT despite having no MANAGE_VOTINGS permission (C3).
    edited = await client.put(
        f"/api/votings/{voting_id}",
        headers=member_headers,
        json={"title": "Zmienione", "recipientsType": "all", "managers": [member_id]},
    )
    assert edited.status_code == 200
    assert edited.json()["title"] == "Zmienione"


async def test_edit_forbidden_for_non_manager(client, seeded) -> None:
    # Voting 2 has no managers; a plain member cannot edit it.
    resp = await client.put(
        "/api/votings/2",
        headers=await _bearer(client, MEMBER),
        json={"title": "x", "recipientsType": "all"},
    )
    assert resp.status_code == 403
    assert resp.json() == {"message": "Brak uprawnień"}


async def test_activate_sets_active(client, seeded) -> None:  # #13
    headers = await _bearer(client, ADMIN)
    resp = await client.post(
        "/api/votings/2/activate",
        headers=headers,
        json={
            "startTime": "2026-09-19T16:00:00",
            "endTime": "2026-09-19T16:30:00",
            "duration": 0.5,
            "delay": 0,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["voting"]["status"] == "active"
    assert body["voting"]["startTime"] == "2026-09-19T16:00:00"


async def test_activate_requires_manage(client, seeded) -> None:
    resp = await client.post(
        "/api/votings/2/activate", headers=await _bearer(client, MEMBER), json={}
    )
    assert resp.status_code == 403


async def test_archive_sets_archived(client, seeded) -> None:  # #14 (API side)
    headers = await _bearer(client, ADMIN)
    resp = await client.post("/api/votings/1/archive", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["voting"]["status"] == "archived"


async def test_attachments_multipart_stored(client, seeded, tmp_path, monkeypatch) -> None:  # #15
    # Redirect uploads to a temp dir so the test never writes into the repo.
    from mparlament.slices.votings.api import router as votings_router
    from mparlament.shared.storage import LocalDiskStorage

    monkeypatch.setattr(
        votings_router._attach, "_storage", LocalDiskStorage(base_dir=tmp_path)
    )
    headers = await _bearer(client, ADMIN)
    files = {"attachment_0": ("nota.txt", b"hello world", "text/plain")}
    resp = await client.post("/api/votings/1/attachments", headers=headers, files=files)
    assert resp.status_code == 200
    assert resp.json() == {"success": True}
    detail = (await client.get("/api/votings/1", headers=headers)).json()
    assert any(a["name"] == "nota.txt" for a in detail["attachments"])


async def test_delete_voting(client, seeded) -> None:  # #16
    headers = await _bearer(client, ADMIN)
    resp = await client.delete("/api/votings/3", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"success": True}
    listing = (await client.get("/api/votings", headers=headers)).json()
    assert all(v["id"] != 3 for v in listing)
