"""SQLAlchemy adapters implementing the resolutions domain ports.

``SqlAlchemyUserDirectory`` / ``SqlAlchemySessionLookup`` reuse doc 02's ``UserModel`` and doc 04's
``SessionModel`` reads to expand ``signedUsers`` and the ``{city, date}`` block — the resolutions
slice depends on those shared collections by projecting the rows directly (loose coupling, C9),
never importing another slice's domain.

``ResolutionLinkedItemStatusUpdater`` is the cascade adapter the votings archive (#14) drives: it
structurally satisfies votings' ``LinkedItemStatusUpdater`` port (``update_status``) and flips a
resolution's ``status`` to accepted/rejected by id, degrading to a no-op when the target is absent.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.slices.auth_identity.infrastructure.models import UserModel
from mparlament.slices.resolutions.domain.entities import (
    Resolution,
    ResolutionSignature,
)
from mparlament.slices.resolutions.domain.ports import DirectoryUser, SessionInfo
from mparlament.slices.resolutions.infrastructure.mappers import (
    apply_resolution,
    to_resolution,
    to_signature,
)
from mparlament.slices.resolutions.infrastructure.models import (
    ResolutionModel,
    ResolutionSignatureModel,
)
from mparlament.slices.sessions.infrastructure.models import SessionModel


class SqlAlchemyResolutionRepository:
    """CRUD + slug/id/session lookups on the ``Resolution`` aggregate (#17-#20)."""

    async def get_by_id(
        self, session: AsyncSession, resolution_id: int
    ) -> Resolution | None:
        row = await session.get(ResolutionModel, resolution_id)
        return to_resolution(row) if row else None

    async def get_by_slug(
        self, session: AsyncSession, slug: str
    ) -> Resolution | None:
        result = await session.execute(
            select(ResolutionModel).where(ResolutionModel.slug == slug)
        )
        row = result.scalar_one_or_none()
        return to_resolution(row) if row else None

    async def list_all(self, session: AsyncSession) -> list[Resolution]:
        result = await session.execute(
            select(ResolutionModel).order_by(ResolutionModel.id)
        )
        return [to_resolution(row) for row in result.scalars().all()]

    async def list_by_session(
        self, session: AsyncSession, session_id: int
    ) -> list[Resolution]:
        result = await session.execute(
            select(ResolutionModel)
            .where(ResolutionModel.session_id == session_id)
            .order_by(ResolutionModel.id)
        )
        return [to_resolution(row) for row in result.scalars().all()]

    async def add(self, session: AsyncSession, resolution: Resolution) -> Resolution:
        row = ResolutionModel()
        apply_resolution(row, resolution)
        session.add(row)
        await session.flush()
        return to_resolution(row)

    async def update(
        self, session: AsyncSession, resolution: Resolution
    ) -> Resolution:
        row = await session.get(ResolutionModel, resolution.id)
        if row is None:
            raise KeyError(resolution.id)
        apply_resolution(row, resolution)
        await session.flush()
        return to_resolution(row)


class SqlAlchemySignatureRepository:
    """Append/remove/look up signature rows (#21/#22, author auto-sign)."""

    async def add(
        self, session: AsyncSession, signature: ResolutionSignature
    ) -> ResolutionSignature:
        row = ResolutionSignatureModel(
            resolution_id=signature.resolutionId,
            user_id=signature.userId,
            timestamp=signature.timestamp,
            type=signature.type,
        )
        session.add(row)
        await session.flush()
        return to_signature(row)

    async def remove(
        self, session: AsyncSession, signature: ResolutionSignature
    ) -> None:
        row = await session.get(ResolutionSignatureModel, signature.id)
        if row is not None:
            await session.delete(row)
            await session.flush()

    async def get(
        self, session: AsyncSession, resolution_id: int, user_id: int
    ) -> ResolutionSignature | None:
        result = await session.execute(
            select(ResolutionSignatureModel).where(
                ResolutionSignatureModel.resolution_id == resolution_id,
                ResolutionSignatureModel.user_id == user_id,
            )
        )
        row = result.scalar_one_or_none()
        return to_signature(row) if row else None

    async def list_by_resolution(
        self, session: AsyncSession, resolution_id: int
    ) -> list[ResolutionSignature]:
        result = await session.execute(
            select(ResolutionSignatureModel)
            .where(ResolutionSignatureModel.resolution_id == resolution_id)
            .order_by(ResolutionSignatureModel.id)
        )
        return [to_signature(row) for row in result.scalars().all()]


class SqlAlchemyUserDirectory:
    """Lists the ``User`` collection as ``DirectoryUser`` for ``signedUsers`` expansion (C9)."""

    async def list_all(self, session: AsyncSession) -> list[DirectoryUser]:
        result = await session.execute(select(UserModel).order_by(UserModel.id))
        return [
            DirectoryUser(id=row.id, name=row.name, club=row.club)
            for row in result.scalars().all()
        ]


class SqlAlchemySessionLookup:
    """Resolves a ``sessionId`` to its ``{city, date}`` block (C10); ``None`` when absent."""

    async def get(
        self, session: AsyncSession, session_id: int | None
    ) -> SessionInfo | None:
        if session_id is None:
            return None
        row = await session.get(SessionModel, session_id)
        if row is None:
            return None
        return SessionInfo(city=row.city, date=row.date)


class ResolutionLinkedItemStatusUpdater:
    """Cascade adapter for the votings archive (#14): flip a resolution's ``status`` by id.

    Structurally satisfies votings' ``LinkedItemStatusUpdater`` port. Ignores non-resolution
    targets and missing rows so the cascade degrades gracefully (README loose coupling).
    """

    def __init__(self, repo: SqlAlchemyResolutionRepository | None = None) -> None:
        self._repo = repo or SqlAlchemyResolutionRepository()

    async def update_status(
        self,
        session: AsyncSession,
        item_type: str,
        item_id: str | None,
        status: str,
    ) -> None:
        if item_type != "resolution" or item_id is None:
            return
        try:
            resolution_id = int(item_id)
        except (TypeError, ValueError):
            return
        resolution = await self._repo.get_by_id(session, resolution_id)
        if resolution is None:
            return
        resolution.status = status
        await self._repo.update(session, resolution)
