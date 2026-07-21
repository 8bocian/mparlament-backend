"""SQLAlchemy adapter implementing the ``UserRepository`` port."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.slices.auth_identity.domain.entities import User
from mparlament.slices.auth_identity.infrastructure.mappers import to_domain
from mparlament.slices.auth_identity.infrastructure.models import UserModel


class SqlAlchemyUserRepository:
    """Loads/lists the ``User`` aggregate from the ``users`` table."""

    async def get_by_id(self, session: AsyncSession, user_id: int) -> User | None:
        row = await session.get(UserModel, user_id)
        return to_domain(row) if row else None

    async def get_by_username(
        self, session: AsyncSession, username: str
    ) -> User | None:
        result = await session.execute(
            select(UserModel).where(UserModel.username == username)
        )
        row = result.scalar_one_or_none()
        return to_domain(row) if row else None

    async def list_all(self, session: AsyncSession) -> list[User]:
        result = await session.execute(select(UserModel).order_by(UserModel.id))
        return [to_domain(row) for row in result.scalars().all()]
