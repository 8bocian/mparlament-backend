"""SQLAlchemy adapters for the amendments slice.

- ``SqlAlchemyAmendmentRepository`` — CRUD-ish persistence for the ``Amendment`` aggregate
  (get/list-by-resolution/list-all/add/update, #23-#28).
- ``AmendmentLinkedItemStatusUpdater`` — the cascade adapter the votings archive (#14) drives:
  structurally satisfies votings' ``LinkedItemStatusUpdater`` port (``update_status``) and flips an
  amendment's ``status`` to accepted/rejected by id, degrading to a no-op for non-amendment targets
  and missing rows (README loose coupling; mirrors ``ResolutionLinkedItemStatusUpdater``).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.slices.amendments.domain.entities import Amendment
from mparlament.slices.amendments.infrastructure.mappers import (
    apply_amendment,
    to_amendment,
)
from mparlament.slices.amendments.infrastructure.models import AmendmentModel


class SqlAlchemyAmendmentRepository:
    """Persistence for the ``Amendment`` aggregate (#23-#28)."""

    async def get_by_id(
        self, session: AsyncSession, amendment_id: int
    ) -> Amendment | None:
        row = await session.get(AmendmentModel, amendment_id)
        return to_amendment(row) if row else None

    async def list_by_resolution(
        self, session: AsyncSession, resolution_id: int
    ) -> list[Amendment]:
        result = await session.execute(
            select(AmendmentModel)
            .where(AmendmentModel.resolution_id == resolution_id)
            .order_by(AmendmentModel.id)
        )
        return [to_amendment(row) for row in result.scalars().all()]

    async def list_all(self, session: AsyncSession) -> list[Amendment]:
        result = await session.execute(
            select(AmendmentModel).order_by(AmendmentModel.id)
        )
        return [to_amendment(row) for row in result.scalars().all()]

    async def add(self, session: AsyncSession, amendment: Amendment) -> Amendment:
        row = AmendmentModel()
        apply_amendment(row, amendment)
        session.add(row)
        await session.flush()
        return to_amendment(row)

    async def update(self, session: AsyncSession, amendment: Amendment) -> Amendment:
        row = await session.get(AmendmentModel, amendment.id)
        if row is None:
            raise KeyError(amendment.id)
        apply_amendment(row, amendment)
        await session.flush()
        return to_amendment(row)


class AmendmentLinkedItemStatusUpdater:
    """Cascade adapter for the votings archive (#14): flip an amendment's ``status`` by id.

    Structurally satisfies votings' ``LinkedItemStatusUpdater`` port. Ignores non-amendment targets
    and missing rows so the cascade degrades gracefully (README loose coupling).
    """

    def __init__(self, repo: SqlAlchemyAmendmentRepository | None = None) -> None:
        self._repo = repo or SqlAlchemyAmendmentRepository()

    async def update_status(
        self,
        session: AsyncSession,
        item_type: str,
        item_id: str | None,
        status: str,
    ) -> None:
        if item_type != "amendment" or item_id is None:
            return
        try:
            amendment_id = int(item_id)
        except (TypeError, ValueError):
            return
        amendment = await self._repo.get_by_id(session, amendment_id)
        if amendment is None:
            return
        amendment.status = status
        await self._repo.update(session, amendment)
