"""Application use cases for the votings slice (doc 05).

Read/write orchestration over the domain ports; the computed projection lives in ``views.py`` and
RBAC is enforced in the router (C3), so these stay unit-testable without FastAPI. The read use
cases fan out one vote query per voting — fine at this scale (KISS); a batch load is a later
optimization if the list grows.

Realtime note (doc 10 / spec §5): ``CastVoteUseCase`` and ``ArchiveVotingUseCase`` are the natural
emit points for ``voteUpdate:<id>`` — deliberately not implemented now (YAGNI); see TODO markers.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.shared.domain import ConflictError, NotFoundError
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


class _VotingUseCase:
    """Shared wiring: the three read collaborators used to build a computed view."""

    def __init__(
        self,
        votings: VotingRepository,
        votes: VoteRepository,
        directory: UserDirectory,
    ) -> None:
        self._votings = votings
        self._votes = votes
        self._directory = directory

    async def _view(
        self, session: AsyncSession, voting: Voting, requester_id: int | None
    ) -> dict:
        votes = await self._votes.list_by_voting(session, voting.id)
        users = await self._directory.list_all(session)
        return build_voting_view(voting, votes, users, requester_id)


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
    """Cast a single vote (spec #12): normalize (C4), enforce single-vote, save."""

    async def execute(
        self, session: AsyncSession, voting_id: int, user_id: int, raw_vote: object
    ) -> dict:
        voting = await self._votings.get(session, voting_id)
        if voting is None:
            raise NotFoundError(_NOT_FOUND)
        value = normalize_vote(raw_vote)
        if await self._votes.get_user_vote(session, voting_id, user_id) is not None:
            raise ConflictError(_ALREADY_VOTED)
        await self._votes.add(session, Vote(votingId=voting_id, userId=user_id, value=value))
        # TODO(doc 10): emit voteUpdate:<voting_id> here.
        return {"vote": value, "message": "Głos został zapisany"}


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
        return {"success": True, "message": "Głosowanie zostało aktywowane", "voting": view}


class ArchiveVotingUseCase(_VotingUseCase):
    """Archive + cascade the result onto the linked item's status (spec #14, C15)."""

    def __init__(
        self,
        votings: VotingRepository,
        votes: VoteRepository,
        directory: UserDirectory,
        linked_updater: LinkedItemStatusUpdater,
    ) -> None:
        super().__init__(votings, votes, directory)
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
        # TODO(doc 10): emit voteUpdate:<voting_id> here.
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
        self, session: AsyncSession, voting_id: int, files: list[tuple[str, bytes, str | None]]
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
