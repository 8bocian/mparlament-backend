"""Domain ports for the resolutions slice (dependency inversion).

The application layer depends on these Protocols; SQLAlchemy adapters live in ``infrastructure``.

- ``ResolutionRepository`` — CRUD + slug/id/session lookups on the ``Resolution`` aggregate.
- ``SignatureRepository`` — append/remove signatures, look one up, list a resolution's signatures.
  The unique ``(resolution_id, user_id)`` constraint is the DB-level single-signature backstop;
  ``get`` is the fast application check.
- ``UserDirectory`` — lists the ``User`` collection as ``DirectoryUser`` so ``signedUsers`` can be
  expanded to ``{name, club}`` without importing another slice's ORM (loose coupling, C9).
- ``SessionLookup`` — resolves a resolution's ``sessionId`` to its ``{city, date}`` block (C10),
  degrading to ``None`` when the sessions slice has no such row.

``resolve_resolution`` (in ``domain.services``) is the shared slug-or-id helper (C5).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.slices.resolutions.domain.entities import (
    Resolution,
    ResolutionSignature,
)


@dataclass(frozen=True)
class DirectoryUser:
    """A ``User`` as ``signedUsers`` reads them (``{name, club}``) keyed by ``id``."""

    id: int
    name: str
    club: str | None = None


@dataclass(frozen=True)
class SessionInfo:
    """The ``{city, date}`` session block the FE reads on a resolution detail (C10)."""

    city: str | None = None
    date: str | None = None


@runtime_checkable
class ResolutionRepository(Protocol):
    """Persistence port for the ``Resolution`` aggregate (#17-#20, cascade)."""

    async def get_by_id(
        self, session: AsyncSession, resolution_id: int
    ) -> Resolution | None: ...

    async def get_by_slug(
        self, session: AsyncSession, slug: str
    ) -> Resolution | None: ...

    async def list_all(self, session: AsyncSession) -> list[Resolution]: ...

    async def list_by_session(
        self, session: AsyncSession, session_id: int
    ) -> list[Resolution]: ...

    async def add(self, session: AsyncSession, resolution: Resolution) -> Resolution: ...

    async def update(
        self, session: AsyncSession, resolution: Resolution
    ) -> Resolution: ...


@runtime_checkable
class SignatureRepository(Protocol):
    """Persistence port for resolution signatures (#21/#22, author auto-sign)."""

    async def add(
        self, session: AsyncSession, signature: ResolutionSignature
    ) -> ResolutionSignature: ...

    async def remove(
        self, session: AsyncSession, signature: ResolutionSignature
    ) -> None: ...

    async def get(
        self, session: AsyncSession, resolution_id: int, user_id: int
    ) -> ResolutionSignature | None: ...

    async def list_by_resolution(
        self, session: AsyncSession, resolution_id: int
    ) -> list[ResolutionSignature]: ...


@runtime_checkable
class UserDirectory(Protocol):
    """Lists the ``User`` collection for ``signedUsers`` expansion (C9)."""

    async def list_all(self, session: AsyncSession) -> list[DirectoryUser]: ...


@runtime_checkable
class SessionLookup(Protocol):
    """Resolves a ``sessionId`` to its ``{city, date}`` block (C10); ``None`` when absent."""

    async def get(
        self, session: AsyncSession, session_id: int | None
    ) -> SessionInfo | None: ...
