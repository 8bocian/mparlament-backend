"""SQLAlchemy adapter for the groups slice (#41).

``SqlAlchemyGroupRepository`` derives the groups from the ``User`` collection — the distinct
non-null ``group`` values with their member counts — so group ids stay equal to ``User.group``
and voting ``selectedGroups`` (C8, C9). No dedicated ``groups`` table is needed (YAGNI): the
``User`` collection is the single source of truth for recipient eligibility.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.slices.auth_identity.infrastructure.models import UserModel
from mparlament.slices.groups_members.domain.entities import Group


class SqlAlchemyGroupRepository:
    """Derives ``Group`` rows from distinct ``User.group`` values (#41)."""

    async def list_all(self, session: AsyncSession) -> list[Group]:
        result = await session.execute(
            select(UserModel.group, func.count(UserModel.id))
            .where(UserModel.group.is_not(None))
            .group_by(UserModel.group)
            .order_by(UserModel.group)
        )
        return [
            Group(id=name, name=name, memberCount=count)
            for name, count in result.all()
        ]
