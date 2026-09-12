"""Domain ports for the votings slice (dependency inversion).

The application layer depends on these Protocols; SQLAlchemy adapters live in ``infrastructure``.

- ``VotingRepository`` — CRUD on the ``Voting`` aggregate.
- ``VoteRepository`` — append a cast vote, look up a user's vote, list a voting's votes
  (the read-time projection counts them). The unique ``(voting_id, user_id)`` constraint is the
  DB-level backstop for the single-vote rule; ``get_user_vote`` is the fast application check.
- ``UserDirectory`` — lists the voter collection as ``DirectoryUser`` for eligibility (C8) and the
  ``{id,name,club}`` expansion the FE reads. Supplied by the auth/users slice so votings never
  imports another slice's ORM (loose coupling, C9).
- ``LinkedItemStatusUpdater`` — cascades a voting's archive result onto its linked
  resolution/amendment status (accepted/rejected) **by id** (spec #14). Kept behind a port so the
  slice degrades gracefully when the target slice is absent (a null adapter is the v1 default).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.slices.votings.domain.entities import DirectoryUser, Voting, Vote


@runtime_checkable
class VotingRepository(Protocol):
    """Persistence port for the ``Voting`` aggregate (#8-#11, #13, #14, #16)."""

    async def get(self, session: AsyncSession, voting_id: int) -> Voting | None: ...

    async def list_all(self, session: AsyncSession) -> list[Voting]: ...

    async def add(self, session: AsyncSession, voting: Voting) -> Voting: ...

    async def update(self, session: AsyncSession, voting: Voting) -> Voting: ...

    async def delete(self, session: AsyncSession, voting_id: int) -> None: ...


@runtime_checkable
class VoteRepository(Protocol):
    """Persistence port for cast votes (#12)."""

    async def add(self, session: AsyncSession, vote: Vote) -> Vote: ...

    async def get_user_vote(
        self, session: AsyncSession, voting_id: int, user_id: int
    ) -> Vote | None: ...

    async def list_by_voting(
        self, session: AsyncSession, voting_id: int
    ) -> list[Vote]: ...

    async def list_user_votes_for_amendments(
        self, session: AsyncSession, user_id: int, amendment_ids: list[int]
    ) -> list[Vote]: ...


@runtime_checkable
class UserDirectory(Protocol):
    """Lists the voter collection for eligibility + FE expansion (C8/C9)."""

    async def list_all(self, session: AsyncSession) -> list[DirectoryUser]: ...


@runtime_checkable
class LinkedItemStatusUpdater(Protocol):
    """Cascades an archived voting's result onto the linked item's status (#14)."""

    async def update_status(
        self,
        session: AsyncSession,
        item_type: str,
        item_id: str | None,
        status: str,
    ) -> None: ...


class NullLinkedItemStatusUpdater:
    """v1 default: no linked slice yet, so the cascade is a graceful no-op (README loose coupling)."""

    async def update_status(
        self,
        session: AsyncSession,
        item_type: str,
        item_id: str | None,
        status: str,
    ) -> None:
        return None
