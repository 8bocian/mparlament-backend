"""Domain port for the amendments slice (dependency inversion).

``AmendmentRepository`` is the only new port: CRUD-ish persistence for the ``Amendment``
aggregate. The parent-resolution lookup reuses the resolutions slice's ``ResolutionRepository`` +
``resolve_resolution`` helper (C5) and its ``SessionLookup`` for the ``{city, date}`` block — the
amendments slice couples to resolutions only by those ports (loose coupling, README).

``update`` is exposed so the votings archive cascade (#14) can flip an amendment's ``status`` to
accepted/rejected via a ``LinkedItemStatusUpdater`` adapter.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.slices.amendments.domain.entities import Amendment


@runtime_checkable
class AmendmentRepository(Protocol):
    """Persistence port for the ``Amendment`` aggregate (#23-#28)."""

    async def get_by_id(
        self, session: AsyncSession, amendment_id: int
    ) -> Amendment | None: ...

    async def list_by_resolution(
        self, session: AsyncSession, resolution_id: int
    ) -> list[Amendment]: ...

    async def list_all(self, session: AsyncSession) -> list[Amendment]: ...

    async def add(self, session: AsyncSession, amendment: Amendment) -> Amendment: ...

    async def update(
        self, session: AsyncSession, amendment: Amendment
    ) -> Amendment: ...
