"""``UserReader`` adapter — supplies the shared identity to ``shared.auth.deps`` (doc 01).

Registered via ``set_user_reader`` at app startup so ``optional_user``/``current_user`` can turn
a token's ``sub`` into the shared ``User`` value object without importing this slice directly.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.shared.auth.user import User as IdentityUser
from mparlament.slices.auth_identity.infrastructure.mappers import to_identity
from mparlament.slices.auth_identity.infrastructure.models import UserModel


class SqlAlchemyUserReader:
    """Concrete ``shared.auth.UserReader``: token subject → shared identity."""

    async def get(self, session: AsyncSession, user_id: int) -> IdentityUser | None:
        row = await session.get(UserModel, user_id)
        return to_identity(row) if row else None
