"""SQLAlchemy adapters implementing the votings domain ports.

``SqlAlchemyUserDirectory`` reuses doc 02's ``UserModel`` read to expand voters as
``DirectoryUser`` — the votings slice depends on the shared ``User`` collection (C9), never the
parliamentarian registry, and stays decoupled from the auth_identity domain by projecting the row
directly.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.slices.auth_identity.infrastructure.models import UserModel
from mparlament.slices.votings.domain.entities import DirectoryUser, Voting, Vote
from mparlament.slices.votings.infrastructure.mappers import (
    apply_voting,
    to_voting,
    to_vote,
)
from mparlament.slices.votings.infrastructure.models import VoteModel, VotingModel


class SqlAlchemyVotingRepository:
    """CRUD on the ``Voting`` aggregate (#8-#11, #13, #14, #16)."""

    async def get(self, session: AsyncSession, voting_id: int) -> Voting | None:
        row = await session.get(VotingModel, voting_id)
        return to_voting(row) if row else None

    async def list_all(self, session: AsyncSession) -> list[Voting]:
        result = await session.execute(select(VotingModel).order_by(VotingModel.id))
        return [to_voting(row) for row in result.scalars().all()]

    async def add(self, session: AsyncSession, voting: Voting) -> Voting:
        row = VotingModel()
        apply_voting(row, voting)
        session.add(row)
        await session.flush()
        return to_voting(row)

    async def update(self, session: AsyncSession, voting: Voting) -> Voting:
        row = await session.get(VotingModel, voting.id)
        if row is None:
            raise KeyError(voting.id)
        apply_voting(row, voting)
        await session.flush()
        return to_voting(row)

    async def delete(self, session: AsyncSession, voting_id: int) -> None:
        row = await session.get(VotingModel, voting_id)
        if row is not None:
            await session.delete(row)
            await session.flush()


class SqlAlchemyVoteRepository:
    """Append + read cast votes (#12). Single-vote is enforced by the unique constraint."""

    async def add(self, session: AsyncSession, vote: Vote) -> Vote:
        row = VoteModel(
            voting_id=vote.votingId, user_id=vote.userId, value=vote.value
        )
        session.add(row)
        await session.flush()
        return to_vote(row)

    async def get_user_vote(
        self, session: AsyncSession, voting_id: int, user_id: int
    ) -> Vote | None:
        result = await session.execute(
            select(VoteModel).where(
                VoteModel.voting_id == voting_id, VoteModel.user_id == user_id
            )
        )
        row = result.scalar_one_or_none()
        return to_vote(row) if row else None

    async def list_by_voting(
        self, session: AsyncSession, voting_id: int
    ) -> list[Vote]:
        result = await session.execute(
            select(VoteModel).where(VoteModel.voting_id == voting_id)
        )
        return [to_vote(row) for row in result.scalars().all()]


class SqlAlchemyUserDirectory:
    """Lists the voter collection as ``DirectoryUser`` for eligibility + FE expansion (C8/C9)."""

    async def list_all(self, session: AsyncSession) -> list[DirectoryUser]:
        result = await session.execute(select(UserModel).order_by(UserModel.id))
        return [
            DirectoryUser(id=row.id, name=row.name, club=row.club, group=row.group)
            for row in result.scalars().all()
        ]
