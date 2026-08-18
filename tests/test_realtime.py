"""Slice 10 — realtime (Socket.IO), doc 10 / spec §5.

Deferred in v1 by build order; implemented once the REST slices are green (README). The FE's
``SocketProvider`` listens for four events (spec §5); this suite verifies each emits with the exact
name + field shape the FE reads, that the write use cases are the emit hook points, that socket and
REST stay in parity (the doc's fallback requirement), and that the inbound ``zoContentUpdated``
round-trips C→S→all and persists.

Layering (CLAUDE.md): kernel unit (port/registry/adapter) → application use-case emits → API
integration (a real REST vote emits through the registered publisher). A live network connect is
out of scope for the unit suite; the connection contract is asserted at the server-wiring level.
"""

from __future__ import annotations

import socketio
import pytest

from mparlament.main import (
    build_socket_server,
    create_asgi_app,
    handle_zo_content_updated,
)
from mparlament.shared.config import get_settings
from mparlament.shared.realtime import (
    NullEventPublisher,
    SocketIOEventPublisher,
    deferred_event_publisher,
    get_event_publisher,
    reset_event_publisher,
    set_event_publisher,
)
from mparlament.slices.auth_identity.infrastructure.seed import DEV_USERS, seed_users
from mparlament.slices.sessions.application.use_cases import (
    AddSpeakerUseCase,
    UpdateCurrentSessionUseCase,
)
from mparlament.slices.sessions.domain.entities import CurrentSession, Speaker
from mparlament.slices.sessions.infrastructure.repository import (
    SqlAlchemyCurrentSessionRepository,
)
from mparlament.slices.votings.application.use_cases import CastVoteUseCase
from mparlament.slices.votings.application.views import build_voting_view
from mparlament.slices.votings.domain.entities import DirectoryUser, Voting, Vote
from mparlament.slices.votings.infrastructure.seed import seed_votings

pytestmark = pytest.mark.anyio

MEMBER = DEV_USERS[1]  # MEMBER1, role=member


# --- spies / fakes ---------------------------------------------------------


class SpyPublisher:
    """Captures every emitted (event, data) so tests can assert names + payloads."""

    def __init__(self) -> None:
        self.events: list[tuple[str, object]] = []

    async def emit(self, event: str, data: object) -> None:
        self.events.append((event, data))


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
        return next(
            (v for v in self._votes if v.votingId == voting_id and v.userId == user_id),
            None,
        )

    async def add(self, session, vote):
        self._votes.append(vote)
        return vote


class _FakeDirectory:
    def __init__(self, users: list[DirectoryUser]) -> None:
        self._users = users

    async def list_all(self, session):
        return self._users


class _FakeCurrentRepo:
    def __init__(self, current: CurrentSession | None = None) -> None:
        self._current = current or CurrentSession()

    async def get(self, session):
        return self._current

    async def save(self, session, current):
        self._current = current
        return current


class _FakeSpeakerRepo:
    async def add(self, session, speaker: Speaker) -> Speaker:
        return Speaker(id=5, name=speaker.name, club=speaker.club, role=speaker.role)


class _FakeSio:
    """Stand-in for a Socket.IO server: records emit calls."""

    def __init__(self) -> None:
        self.emitted: list[tuple[str, object]] = []

    async def emit(self, event, data=None, **kwargs):
        self.emitted.append((event, data))


@pytest.fixture(autouse=True)
def _reset_publisher():
    """Isolate the process-global publisher from other tests / the rest of the suite."""
    yield
    reset_event_publisher()


# --- kernel unit: port + registry + deferred proxy -------------------------


async def test_null_publisher_is_noop() -> None:
    # The v1 default: emitting is free and never raises.
    assert await NullEventPublisher().emit("x", {"a": 1}) is None


def test_registry_defaults_to_null() -> None:
    assert isinstance(get_event_publisher(), NullEventPublisher)


async def test_deferred_publisher_late_binds_to_registered() -> None:
    spy = SpyPublisher()
    set_event_publisher(spy)
    # The proxy the use-case singletons hold resolves the *current* global at emit time.
    await deferred_event_publisher.emit("evt", {"n": 1})
    assert spy.events == [("evt", {"n": 1})]


async def test_socketio_adapter_broadcasts_via_server() -> None:
    sio = _FakeSio()
    await SocketIOEventPublisher(sio).emit("voteUpdate:9", {"votedCount": 2})
    assert sio.emitted == [("voteUpdate:9", {"votedCount": 2})]


# --- application unit: voteUpdate emit + REST/socket parity ----------------
#
# Checklist #2 (cast emits) and #5 (payload equals the REST detail fields).

_VOTERS = [
    DirectoryUser(id=1, name="Anna", club="KO", group="A"),
    DirectoryUser(id=2, name="Piotr", club="PiS", group="B"),
    DirectoryUser(id=3, name="Ola", club="KO", group="A"),
]


async def test_cast_vote_emits_voteupdate_with_exact_fields() -> None:  # checklist #2
    voting = Voting(id=7, title="V", recipientsType="all")
    votes: list[Vote] = []
    spy = SpyPublisher()
    use_case = CastVoteUseCase(
        _FakeVotingRepo(voting), _FakeVoteRepo(votes), _FakeDirectory(_VOTERS), spy
    )

    await use_case.execute(session=None, voting_id=7, user_id=1, raw_vote="for")

    assert len(spy.events) == 1
    event, payload = spy.events[0]
    assert event == "voteUpdate:7"  # event name embeds the voting id (spec §5)
    assert set(payload) == {
        "votedCount",
        "votesFor",
        "votesAgainst",
        "abstained",
        "votedUsers",
        "notVotedUsers",
    }
    assert payload["votedCount"] == 1
    assert payload["votesFor"] == 1
    assert payload["votesAgainst"] == 0
    assert payload["abstained"] == 0
    assert payload["votedUsers"] == [{"id": 1, "name": "Anna", "club": "KO"}]
    assert {u["id"] for u in payload["notVotedUsers"]} == {2, 3}


async def test_voteupdate_payload_matches_rest_view() -> None:  # checklist #5 (parity)
    voting = Voting(id=7, title="V", recipientsType="all")
    votes: list[Vote] = []
    spy = SpyPublisher()
    use_case = CastVoteUseCase(
        _FakeVotingRepo(voting), _FakeVoteRepo(votes), _FakeDirectory(_VOTERS), spy
    )

    await use_case.execute(session=None, voting_id=7, user_id=2, raw_vote="against")

    _event, payload = spy.events[0]
    rest_view = build_voting_view(voting, votes, _VOTERS, requester_id=None)
    # Every socket field equals the corresponding REST detail field (doc 10 fallback parity).
    for key in payload:
        assert payload[key] == rest_view[key]


# --- application unit: session events (checklist #4) -----------------------


async def test_update_emits_schedule_updated() -> None:
    spy = SpyPublisher()
    use_case = UpdateCurrentSessionUseCase(_FakeCurrentRepo(), spy)
    schedule = [{"time": "10:00", "title": "Otwarcie", "status": "active"}]

    await use_case.execute(session=None, patch={"schedule": schedule})

    assert spy.events == [("scheduleUpdated", schedule)]


async def test_update_emits_speaker_updated() -> None:
    spy = SpyPublisher()
    use_case = UpdateCurrentSessionUseCase(_FakeCurrentRepo(), spy)
    speaker = {"name": "Jan", "club": "KO", "role": "poseł", "time": "10:05"}

    await use_case.execute(session=None, patch={"currentSpeaker": speaker})

    assert spy.events == [("speakerUpdated", speaker)]


async def test_update_emits_zo_content_updated() -> None:
    spy = SpyPublisher()
    use_case = UpdateCurrentSessionUseCase(_FakeCurrentRepo(), spy)

    await use_case.execute(session=None, patch={"zoContent": "Treść ZO"})

    assert spy.events == [("zoContentUpdated", "Treść ZO")]


async def test_update_emits_only_changed_keys() -> None:
    spy = SpyPublisher()
    use_case = UpdateCurrentSessionUseCase(_FakeCurrentRepo(), spy)

    # A patch touching neither schedule/speaker/zoContent emits nothing.
    await use_case.execute(session=None, patch={"title": "Nowy tytuł"})
    assert spy.events == []

    # A combined patch emits one event per relevant key, in a stable order.
    await use_case.execute(
        session=None, patch={"schedule": [], "zoContent": "x"}
    )
    assert [e[0] for e in spy.events] == ["scheduleUpdated", "zoContentUpdated"]


async def test_add_speaker_emits_speaker_updated() -> None:
    spy = SpyPublisher()
    use_case = AddSpeakerUseCase(_FakeSpeakerRepo(), spy)

    await use_case.execute(session=None, name="Ewa", club="KO", role="marszałek")

    assert spy.events == [
        ("speakerUpdated", {"name": "Ewa", "club": "KO", "role": "marszałek", "time": None})
    ]


# --- server wiring + inbound handler (checklist #1, #3) --------------------


def test_socket_server_registers_connection_and_inbound_handlers() -> None:  # checklist #1
    sio = build_socket_server(get_settings())
    assert isinstance(sio, socketio.AsyncServer)
    handlers = sio.handlers["/"]
    assert "connect" in handlers
    assert "disconnect" in handlers
    assert "zoContentUpdated" in handlers  # inbound C→S (spec §5)


async def test_inbound_zo_content_persists_and_rebroadcasts(db_engine) -> None:  # checklist #3
    from sqlalchemy.ext.asyncio import async_sessionmaker

    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    spy = SpyPublisher()

    await handle_zo_content_updated(factory, "Nowa treść ZO", spy)

    # Rebroadcast to all clients rides on the use case's emit (S→C).
    assert spy.events == [("zoContentUpdated", "Nowa treść ZO")]
    # And it persisted, so the REST fallback reads the same value.
    async with factory() as session:
        current = await SqlAlchemyCurrentSessionRepository().get(session)
    assert current is not None and current.zoContent == "Nowa treść ZO"


def test_create_asgi_app_wraps_fastapi_and_installs_publisher() -> None:  # checklist #1
    asgi = create_asgi_app()
    assert isinstance(asgi, socketio.ASGIApp)
    # The concrete publisher is now live, so REST write use cases emit over Socket.IO.
    assert isinstance(get_event_publisher(), SocketIOEventPublisher)


# --- API integration: a real REST vote emits through the registry ----------


@pytest.fixture
async def seeded(async_session):
    await seed_users(async_session)
    await seed_votings(async_session)
    await async_session.commit()


async def _bearer(client, user) -> dict[str, str]:
    resp = await client.post(
        "/api/auth/login",
        json={"username": user["username"], "password": user["password"]},
    )
    return {"Authorization": f"Bearer {resp.json()['token']}"}


async def test_rest_vote_emits_voteupdate_end_to_end(client, seeded) -> None:  # checklist #2/#5
    spy = SpyPublisher()
    set_event_publisher(spy)  # the router use cases hold the deferred proxy → resolves to spy
    headers = await _bearer(client, MEMBER)

    resp = await client.post("/api/votings/1/vote", headers=headers, json={"vote": "for"})
    assert resp.status_code == 200

    assert len(spy.events) == 1
    event, payload = spy.events[0]
    assert event == "voteUpdate:1"

    # Parity: the emitted live-tally fields equal the REST detail's same fields.
    detail = (await client.get("/api/votings/1", headers=headers)).json()
    for key in payload:
        assert payload[key] == detail[key]
