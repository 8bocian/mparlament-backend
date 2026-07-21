"""``UserReader`` port + registry (dependency inversion for identity loading).

The auth dependencies in ``deps.py`` must turn a token's ``sub`` into a :class:`User`, but the
``User`` table is owned by the auth_identity slice (02). To avoid a hard import cycle the slice
*registers* a concrete reader at startup via :func:`set_user_reader`; until then a null reader
returns ``None`` (so slice-01 works in isolation and unauthenticated paths stay valid).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.shared.auth.user import User


@runtime_checkable
class UserReader(Protocol):
    """Loads the authenticated ``User`` for a token subject."""

    async def get(self, session: AsyncSession, user_id: int) -> User | None: ...


class _NullUserReader:
    """Fallback used before the auth_identity slice registers a real reader."""

    async def get(self, session: AsyncSession, user_id: int) -> User | None:
        return None


_reader: UserReader = _NullUserReader()


def set_user_reader(reader: UserReader) -> None:
    """Register the concrete reader (called by the auth_identity slice wiring)."""
    global _reader
    _reader = reader


def get_user_reader() -> UserReader:
    """Return the currently registered ``UserReader``."""
    return _reader
