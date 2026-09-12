"""Application use cases for the votings slice (doc 05).

Read/write orchestration over the domain ports; the computed projection lives in ``views.py`` and
RBAC is enforced in the router (C3), so these stay unit-testable without FastAPI. The read use
cases fan out one vote query per voting — fine at this scale (KISS); a batch load is a later
optimization if the list grows.

Realtime note (doc 10 / spec §5): ``CastVoteUseCase`` and ``ArchiveVotingUseCase`` emit
``voteUpdate:<id>`` at commit time via the injected :class:`EventPublisher` port. The payload is
derived from the same read projection the REST detail endpoint returns (``build_voting_view``), so
socket and REST stay in parity (doc 10 "fallback parity"). The default publisher is a no-op, so the
emit is free until Socket.IO is wired.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.shared.domain import ConflictError, NotFoundError
from mparlament.shared.realtime import EventPublisher, NullEventPublisher
from mparlament.slices.votings.application.views import build_voting_view
from mparlament.slices.votings.domain.entities import (
    Voting,
    Vote,
    normalize_vote,
)
from mparlament.slices.votings.domain.ports import (
    LinkedItemStatusUpdater,
    UserDirectory,
    VoteRepository,
    VotingRepository,
)

_NOT_FOUND = "Nie znaleziono głosowania"
_ALREADY_VOTED = "Użytkownik już oddał głos"


# The live-tally fields the FE reads from a ``voteUpdate:<id>`` event — a subset of the REST
# detail view, so socket and polling stay in parity (doc 10 / spec §5).
_VOTE_UPDATE_KEYS = (
    "votedCount",
    "votesFor",
    "votesAgainst",
    "abstained",
    "votedUsers",
    "notVotedUsers",
)


class _VotingUseCase:
    """Shared wiring: the three read collaborators used to build a computed view."""

    def __init__(
        self,
        votings: VotingRepository,
        votes: VoteRepository,
        directory: UserDirectory,
        publisher: EventPublisher | None = None,
    ) -> None:
        self._votings = votings
        self._votes = votes
        self._directory = directory
        self._publisher = publisher or NullEventPublisher()

    async def _view(
        self, session: AsyncSession, voting: Voting, requester_id: int | None
    ) -> dict:
        votes = await self._votes.list_by_voting(session, voting.id)
        users = await self._directory.list_all(session)
        return build_voting_view(voting, votes, users, requester_id)

    async def _emit_vote_update(self, session: AsyncSession, voting: Voting) -> None:
        """Emit ``voteUpdate:<id>`` with the requester-agnostic live tally (doc 10)."""
        view = await self._view(session, voting, requester_id=None)
        payload = {key: view[key] for key in _VOTE_UPDATE_KEYS}
        await self._publisher.emit(f"voteUpdate:{voting.id}", payload)


class ListVotingsUseCase(_VotingUseCase):
    """All votings with computed fields — a **bare array** (spec #8, C10)."""

    async def execute(
        self, session: AsyncSession, requester_id: int | None
    ) -> list[dict]:
        votings = await self._votings.list_all(session)
        users = await self._directory.list_all(session)
        views = []
        for voting in votings:
            votes = await self._votes.list_by_voting(session, voting.id)
            views.append(build_voting_view(voting, votes, users, requester_id))
        return views


class GetVotingUseCase(_VotingUseCase):
    """Full voting + computed lists (spec #9); 404 when absent."""

    async def execute(
        self, session: AsyncSession, voting_id: int, requester_id: int | None
    ) -> dict:
        voting = await self._votings.get(session, voting_id)
        if voting is None:
            raise NotFoundError(_NOT_FOUND)
        return await self._view(session, voting, requester_id)


class CreateVotingUseCase(_VotingUseCase):
    """Persist a new voting (RBAC in router); returns the created view with ``id`` (spec #10)."""

    async def execute(
        self, session: AsyncSession, voting: Voting, requester_id: int | None
    ) -> dict:
        created = await self._votings.add(session, voting)
        return await self._view(session, created, requester_id)


class UpdateVotingUseCase(_VotingUseCase):
    """Replace a voting's editable fields (spec #11); 404 when absent."""

    async def execute(
        self,
        session: AsyncSession,
        voting_id: int,
        new_voting: Voting,
        requester_id: int | None,
    ) -> dict:
        existing = await self._votings.get(session, voting_id)
        if existing is None:
            raise NotFoundError(_NOT_FOUND)
        new_voting.id = voting_id
        updated = await self._votings.update(session, new_voting)
        return await self._view(session, updated, requester_id)


class CastVoteUseCase(_VotingUseCase):
    """Cast a single vote (spec #12): normalize (C4), enforce single-vote, save.

    Conflict guard: when the voting is linked to an amendment and the vote is ``for``,
    we check whether the user has already voted ``for`` on a conflicting amendment of
    the same resolution (port of the FE's ``detectAllConflicts`` guard).
    """

    async def execute(
        self, session: AsyncSession, voting_id: int, user_id: int, raw_vote: object
    ) -> dict:
        voting = await self._votings.get(session, voting_id)
        if voting is None:
            raise NotFoundError(_NOT_FOUND)
        value = normalize_vote(raw_vote)
        if await self._votes.get_user_vote(session, voting_id, user_id) is not None:
            raise ConflictError(_ALREADY_VOTED)

        # Conflict guard (spec: only amendments + only "for").
        if (
            value == "for"
            and voting.linkedItemType == "amendment"
            and voting.linkedItemId
        ):
            conflict = await self._check_amendment_conflict(
                session, int(voting.linkedItemId), user_id
            )
            if conflict is not None:
                from mparlament.shared.domain import AmendmentConflictError

                raise AmendmentConflictError(conflict["message"], payload=conflict)

        await self._votes.add(
            session, Vote(votingId=voting_id, userId=user_id, value=value)
        )
        await self._emit_vote_update(session, voting)
        return {"vote": value, "message": "Głos został zapisany"}

    async def _check_amendment_conflict(
        self, session: AsyncSession, amendment_id: int, user_id: int
    ) -> dict | None:
        """Returns a conflict payload when the user's prior votes conflict; else ``None``."""
        from mparlament.slices.amendments.domain.services import detect_all_conflicts
        from mparlament.slices.amendments.infrastructure.repository import (
            SqlAlchemyAmendmentRepository,
        )

        amendments_repo = SqlAlchemyAmendmentRepository()
        current = await amendments_repo.get_by_id(session, amendment_id)
        if current is None or current.resolutionId is None:
            return None

        siblings = await amendments_repo.list_by_resolution(
            session, current.resolutionId
        )
        with_conflicts = detect_all_conflicts(siblings)
        current_view = next(
            (a for a in with_conflicts if a["id"] == amendment_id), None
        )
        if not current_view or not current_view.get("conflictsWith"):
            return None

        conflicting_ids = set(current_view["conflictsWith"])
        prior_votes = await self._votes.list_user_votes_for_amendments(
            session, user_id, list(conflicting_ids)
        )
        has_conflict = any(v.value == "for" for v in prior_votes)
        if not has_conflict:
            return None

        return {
            "success": False,
            "message": (
                "Nie możesz głosować ZA tą poprawką, ponieważ jest sprzeczna "
                "z inną poprawką, którą poparłeś."
            ),
            "conflictsWith": current_view["conflictsWith"],
            "conflictReason": current_view.get("conflictReason"),
            "conflictFragment": current_view.get("conflictFragment"),
        }


class ActivateVotingUseCase(_VotingUseCase):
    """Set ``status="active"`` + times (spec #13, C15); 404 when absent."""

    async def execute(
        self,
        session: AsyncSession,
        voting_id: int,
        startTime: str | None,
        endTime: str | None,
        duration: object,
        delay: object,
        requester_id: int | None,
    ) -> dict:
        voting = await self._votings.get(session, voting_id)
        if voting is None:
            raise NotFoundError(_NOT_FOUND)
        voting.activate(startTime, endTime, duration, delay)
        updated = await self._votings.update(session, voting)
        view = await self._view(session, updated, requester_id)
        return {
            "success": True,
            "message": "Głosowanie zostało aktywowane",
            "voting": view,
        }


class ArchiveVotingUseCase(_VotingUseCase):
    """Archive + cascade the result onto the linked item's status (spec #14, C15)."""

    def __init__(
        self,
        votings: VotingRepository,
        votes: VoteRepository,
        directory: UserDirectory,
        linked_updater: LinkedItemStatusUpdater,
        publisher: EventPublisher | None = None,
    ) -> None:
        super().__init__(votings, votes, directory, publisher)
        self._linked = linked_updater

    async def execute(
        self, session: AsyncSession, voting_id: int, requester_id: int | None
    ) -> dict:
        voting = await self._votings.get(session, voting_id)
        if voting is None:
            raise NotFoundError(_NOT_FOUND)
        voting.archive()
        updated = await self._votings.update(session, voting)

        if voting.linkedItemType and voting.linkedItemType != "none":
            votes = await self._votes.list_by_voting(session, voting_id)
            votes_for = sum(1 for v in votes if v.value == "for")
            votes_against = sum(1 for v in votes if v.value == "against")
            result = "accepted" if votes_for > votes_against else "rejected"
            await self._linked.update_status(
                session, voting.linkedItemType, voting.linkedItemId, result
            )
        await self._emit_vote_update(session, updated)
        view = await self._view(session, updated, requester_id)
        return {"success": True, "voting": view}


class AddAttachmentsUseCase(_VotingUseCase):
    """Store uploaded files + append their metadata to the voting (spec #15, fire-and-forget)."""

    def __init__(
        self,
        votings: VotingRepository,
        votes: VoteRepository,
        directory: UserDirectory,
        storage,
        max_bytes: int = 10 * 1024 * 1024,
    ) -> None:
        super().__init__(votings, votes, directory)
        self._storage = storage
        self._max_bytes = max_bytes

    async def execute(
        self,
        session: AsyncSession,
        voting_id: int,
        files: list[tuple[str, bytes, str | None]],
    ) -> dict:
        from mparlament.shared.domain import ValidationError
        from mparlament.slices.votings.domain.entities import Attachment

        voting = await self._votings.get(session, voting_id)
        if voting is None:
            raise NotFoundError(_NOT_FOUND)

        for name, data, content_type in files:
            if len(data) > self._max_bytes:
                raise ValidationError("Plik przekracza dozwolony rozmiar")
            await self._storage.save(f"votings/{voting_id}", name, data)
            voting.attachments.append(
                Attachment(
                    id=len(voting.attachments) + 1,
                    name=name,
                    size=len(data),
                    type=content_type,
                    uploadDate=None,
                )
            )
        await self._votings.update(session, voting)
        return {"success": True}


class DeleteVotingUseCase(_VotingUseCase):
    """Delete a voting (spec #16, handler-only)."""

    async def execute(self, session: AsyncSession, voting_id: int) -> dict:
        await self._votings.delete(session, voting_id)
        return {"success": True}
