"""SQLAlchemy adapters for the parliamentarians & clubs slice (#29-#36).

- ``SqlAlchemyParliamentarianRepository`` — CRUD + ``upsert`` (POST-as-upsert, C7). ``upsert``
  updates in place when the body carries an ``id`` of an existing row, else inserts (no duplicate).
- ``SqlAlchemyClubRepository`` — CRUD; ``delete`` unlinks members (``club_id→null``) explicitly
  before removing the club so the cascade is DB-agnostic (#36).
"""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.slices.parliamentarians_clubs.domain.entities import (
    Club,
    Parliamentarian,
)
from mparlament.slices.parliamentarians_clubs.infrastructure.mappers import (
    apply_club,
    apply_parliamentarian,
    to_club,
    to_parliamentarian,
)
from mparlament.slices.parliamentarians_clubs.infrastructure.models import (
    ClubModel,
    ParliamentarianModel,
)


class SqlAlchemyParliamentarianRepository:
    """Persistence for the ``Parliamentarian`` aggregate (#29-#32)."""

    async def get_by_id(
        self, session: AsyncSession, parliamentarian_id: int
    ) -> Parliamentarian | None:
        row = await session.get(ParliamentarianModel, parliamentarian_id)
        return to_parliamentarian(row) if row else None

    async def list_all(self, session: AsyncSession) -> list[Parliamentarian]:
        result = await session.execute(
            select(ParliamentarianModel).order_by(ParliamentarianModel.id)
        )
        return [to_parliamentarian(row) for row in result.scalars().all()]

    async def add(
        self, session: AsyncSession, parliamentarian: Parliamentarian
    ) -> Parliamentarian:
        row = ParliamentarianModel()
        apply_parliamentarian(row, parliamentarian)
        session.add(row)
        await session.flush()
        return to_parliamentarian(row)

    async def update(
        self, session: AsyncSession, parliamentarian: Parliamentarian
    ) -> Parliamentarian:
        row = await session.get(ParliamentarianModel, parliamentarian.id)
        if row is None:
            raise KeyError(parliamentarian.id)
        apply_parliamentarian(row, parliamentarian)
        await session.flush()
        return to_parliamentarian(row)

    async def upsert(
        self, session: AsyncSession, parliamentarian: Parliamentarian
    ) -> Parliamentarian:
        """Update in place when ``id`` matches an existing row, else insert (C7)."""
        if parliamentarian.id is not None:
            existing = await session.get(ParliamentarianModel, parliamentarian.id)
            if existing is not None:
                apply_parliamentarian(existing, parliamentarian)
                await session.flush()
                return to_parliamentarian(existing)
        return await self.add(session, parliamentarian)

    async def delete(
        self, session: AsyncSession, parliamentarian_id: int
    ) -> bool:
        row = await session.get(ParliamentarianModel, parliamentarian_id)
        if row is None:
            return False
        await session.delete(row)
        await session.flush()
        return True


class SqlAlchemyClubRepository:
    """Persistence for the ``Club`` aggregate (#33-#36)."""

    async def get_by_id(self, session: AsyncSession, club_id: int) -> Club | None:
        row = await session.get(ClubModel, club_id)
        return to_club(row) if row else None

    async def list_all(self, session: AsyncSession) -> list[Club]:
        result = await session.execute(select(ClubModel).order_by(ClubModel.id))
        return [to_club(row) for row in result.scalars().all()]

    async def add(self, session: AsyncSession, club: Club) -> Club:
        row = ClubModel()
        apply_club(row, club)
        session.add(row)
        await session.flush()
        return to_club(row)

    async def update(self, session: AsyncSession, club: Club) -> Club:
        row = await session.get(ClubModel, club.id)
        if row is None:
            raise KeyError(club.id)
        apply_club(row, club)
        await session.flush()
        return to_club(row)

    async def delete(self, session: AsyncSession, club_id: int) -> bool:
        """Unlink members (``club_id→null``) then delete the club (#36)."""
        row = await session.get(ClubModel, club_id)
        if row is None:
            return False
        await session.execute(
            update(ParliamentarianModel)
            .where(ParliamentarianModel.club_id == club_id)
            .values(club_id=None)
        )
        await session.delete(row)
        await session.flush()
        return True
