"""Application use cases for the resolutions slice (doc 06).

Read/write orchestration over the domain ports; the projections live in ``views.py`` and identity
is resolved in the router (C2), so these stay unit-testable without FastAPI. Signature counts are
kept in sync with the rows on every sign/unsign (the ``signatures`` scalar the FE reads).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.shared.domain import ConflictError, NotFoundError
from mparlament.slices.resolutions.application.dtos import ResolutionCreateData
from mparlament.slices.resolutions.application.views import (
    current_user_block,
    resolution_dict,
    signed_user,
)
from mparlament.slices.resolutions.domain.entities import (
    AUTHOR,
    SIGNATURE,
    Resolution,
    ResolutionSignature,
    slugify,
)
from mparlament.slices.resolutions.domain.ports import (
    ResolutionRepository,
    SessionLookup,
    SignatureRepository,
    UserDirectory,
)
from mparlament.slices.resolutions.domain.services import resolve_resolution

_NOT_FOUND = "Nie znaleziono uchwały"
_ALREADY_SIGNED = "Już podpisałeś tę uchwałę"
_NO_SIGNATURE = "Nie znaleziono podpisu"
_SIGNATURE_REMOVED = "Podpis został usunięty"


def _today() -> str:
    return dt.date.today().isoformat()  # "YYYY-MM-DD" (C13)


def _now_iso() -> str:
    return dt.datetime.now(tz=dt.timezone.utc).isoformat()


class _ResolutionUseCase:
    """Shared wiring for the read/write collaborators."""

    def __init__(
        self,
        resolutions: ResolutionRepository,
        signatures: SignatureRepository,
        directory: UserDirectory,
        sessions: SessionLookup,
    ) -> None:
        self._resolutions = resolutions
        self._signatures = signatures
        self._directory = directory
        self._sessions = sessions

    async def _refresh_count(
        self, session: AsyncSession, resolution: Resolution
    ) -> Resolution:
        """Recompute ``signatures`` from the rows and persist (keeps the FE scalar in sync)."""
        rows = await self._signatures.list_by_resolution(session, resolution.id)
        resolution.signatures = len(rows)
        return await self._resolutions.update(session, resolution)


class ListResolutionsUseCase(_ResolutionUseCase):
    """All resolutions wrapped as ``{resolutions: [...]}`` (spec #17, C10)."""

    async def execute(self, session: AsyncSession) -> dict:
        resolutions = await self._resolutions.list_all(session)
        return {"resolutions": [resolution_dict(r) for r in resolutions]}


class GetResolutionUseCase(_ResolutionUseCase):
    """Resolution detail (spec #18/#18b): ``{resolution, signedUsers, session, currentUser?}``.

    ``param`` is polymorphic (slug or id, C5); ``currentUser`` is included only when identity is
    known (``requester_id`` not ``None``, C2). 404 → ``Nie znaleziono uchwały``.
    """

    async def execute(
        self, session: AsyncSession, param: str, requester_id: int | None
    ) -> dict:
        resolution = await resolve_resolution(session, param, self._resolutions)
        if resolution is None:
            raise NotFoundError(_NOT_FOUND)

        signatures = await self._signatures.list_by_resolution(session, resolution.id)
        users = await self._directory.list_all(session)
        users_by_id = {u.id: u for u in users}
        session_info = await self._sessions.get(session, resolution.sessionId)

        body: dict = {
            "resolution": resolution_dict(resolution),
            "signedUsers": [signed_user(s, users_by_id) for s in signatures],
            "session": (
                {"city": session_info.city, "date": session_info.date}
                if session_info
                else None
            ),
        }
        if requester_id is not None:
            body["currentUser"] = current_user_block(
                resolution, signatures, requester_id
            )
        return body


class CreateResolutionUseCase(_ResolutionUseCase):
    """Persist a new resolution from the multipart body (#19): slug, pending, author auto-sign."""

    def __init__(
        self,
        resolutions: ResolutionRepository,
        signatures: SignatureRepository,
        directory: UserDirectory,
        sessions: SessionLookup,
        storage,
    ) -> None:
        super().__init__(resolutions, signatures, directory, sessions)
        self._storage = storage

    async def execute(
        self,
        session: AsyncSession,
        file_bytes: bytes,
        upload_name: str | None,
        data_json: str | bytes | None,
    ) -> dict:
        data = ResolutionCreateData.parse(data_json)

        # Slug is deterministic + collision-safe against the slugs already in use (C12).
        taken = {r.slug for r in await self._resolutions.list_all(session)}
        file_name = data.fileName or upload_name

        file_path = None
        if file_name is not None:
            file_path = await self._storage.save("resolutions", file_name, file_bytes)

        resolution = Resolution(
            **data.as_kwargs(),
            slug=slugify(data.title, taken),
            signatures=1,
            status="pending",
            createdAt=_today(),
            filePath=file_path,
        )
        resolution.fileName = file_name
        created = await self._resolutions.add(session, resolution)

        # Author auto-signature (spec §2 ResolutionSignature; type="author").
        if created.authorId is not None:
            await self._signatures.add(
                session,
                ResolutionSignature(
                    resolutionId=created.id,
                    userId=created.authorId,
                    timestamp=_now_iso(),
                    type=AUTHOR,
                ),
            )
        return resolution_dict(created)


class SignResolutionUseCase(_ResolutionUseCase):
    """A member signs a resolution (spec #21): single-signature, count kept in sync."""

    async def execute(
        self, session: AsyncSession, resolution_id: int, user_id: int
    ) -> dict:
        resolution = await self._resolutions.get_by_id(session, resolution_id)
        if resolution is None:
            raise NotFoundError(_NOT_FOUND)
        if await self._signatures.get(session, resolution_id, user_id) is not None:
            raise ConflictError(_ALREADY_SIGNED)
        await self._signatures.add(
            session,
            ResolutionSignature(
                resolutionId=resolution_id,
                userId=user_id,
                timestamp=_now_iso(),
                type=SIGNATURE,
            ),
        )
        await self._refresh_count(session, resolution)
        return {"success": True}


class UnsignResolutionUseCase(_ResolutionUseCase):
    """Remove a signer's signature (spec #22): author-protected; count kept in sync."""

    async def execute(
        self, session: AsyncSession, resolution_id: int, user_id: int
    ) -> dict:
        resolution = await self._resolutions.get_by_id(session, resolution_id)
        if resolution is None:
            raise NotFoundError(_NOT_FOUND)
        signature = await self._signatures.get(session, resolution_id, user_id)
        if signature is None:
            raise NotFoundError(_NO_SIGNATURE)
        signature.ensure_removable()  # 403 for the author's auto-signature (C11)
        await self._signatures.remove(session, signature)
        await self._refresh_count(session, resolution)
        return {"success": True, "message": _SIGNATURE_REMOVED}


class ListSessionResolutionsUseCase(_ResolutionUseCase):
    """Resolutions of one session (spec #20): ``{resolutions, sessionId, count}``."""

    async def execute(self, session: AsyncSession, session_id: int) -> dict:
        resolutions = await self._resolutions.list_by_session(session, session_id)
        views = [resolution_dict(r) for r in resolutions]
        return {"resolutions": views, "sessionId": session_id, "count": len(views)}


class DeleteResolutionUseCase(_ResolutionUseCase):
    """Delete a resolution (#22b). DB-level cascade removes signatures + amendments."""

    async def execute(self, session: AsyncSession, resolution_id: int) -> dict:
        resolution = await self._resolutions.get_by_id(session, resolution_id)
        if resolution is None:
            raise NotFoundError(_NOT_FOUND)
        await self._resolutions.delete(session, resolution_id)
        return {"success": True, "message": "Uchwała została usunięta"}
