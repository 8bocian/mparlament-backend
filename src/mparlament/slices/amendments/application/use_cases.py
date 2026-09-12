"""Application use cases for the amendments slice (doc 07).

Read/write orchestration over the amendment repository plus the resolutions slice's parent lookup
(``resolve_resolution``, C5) and ``SessionLookup``. Projections live in ``views.py`` and identity
is resolved in the router (C2), so these stay unit-testable without FastAPI.

- ``ListResolutionAmendmentsUseCase`` (#23/#23b) — polymorphic parent → ``{resolution, session,
  amendments}``.
- ``CreateAmendmentUseCase`` (#24) — resolve parent (404), server-assign ``id/createdAt/
  resolutionId`` → ``{success, amendment}``.
- ``GetAmendmentUnderResolutionUseCase`` (#25) — ``{resolution, amendment, session}``; 404 poprawki.
- ``ListAmendmentsUseCase`` (#26) — **bare array**.
- ``GetAmendmentUseCase`` (#27) — ``{data: {...amendment, resolution:{id,title,slug}}}``.
- ``WithdrawAmendmentUseCase`` (#28) — author-only withdraw (404/400/403).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.shared.domain import NotFoundError
from mparlament.slices.amendments.application.dtos import AmendmentCreateBody
from mparlament.slices.amendments.application.views import amendment_dict
from mparlament.slices.amendments.domain.entities import Amendment
from mparlament.slices.amendments.domain.ports import AmendmentRepository
from mparlament.slices.resolutions.domain.entities import Resolution
from mparlament.slices.resolutions.domain.ports import (
    ResolutionRepository,
    SessionLookup,
)
from mparlament.slices.resolutions.domain.services import resolve_resolution

_AMENDMENT_NOT_FOUND = "Nie znaleziono poprawki"
_RESOLUTION_NOT_FOUND = "Nie znaleziono uchwały"


def _today() -> str:
    return dt.date.today().isoformat()  # "YYYY-MM-DD" (C13)


def _session_block(info) -> dict | None:
    return {"city": info.city, "date": info.date} if info else None


def _resolution_ref(resolution: Resolution) -> dict:
    """The ``{title, slug}`` parent ref the composite amendment wrappers carry (#23/#25)."""
    return {"title": resolution.title, "slug": resolution.slug}


class _AmendmentUseCase:
    """Shared wiring: amendment repo + resolutions parent lookup + session block."""

    def __init__(
        self,
        amendments: AmendmentRepository,
        resolutions: ResolutionRepository,
        sessions: SessionLookup,
    ) -> None:
        self._amendments = amendments
        self._resolutions = resolutions
        self._sessions = sessions

    async def _resolve_parent(self, session: AsyncSession, param: str) -> Resolution:
        resolution = await resolve_resolution(session, param, self._resolutions)
        if resolution is None:
            raise NotFoundError(_RESOLUTION_NOT_FOUND)
        return resolution


class ListResolutionAmendmentsUseCase(_AmendmentUseCase):
    """Amendments of one resolution (spec #23/#23b): ``{resolution, session, amendments}``.

    ``param`` is polymorphic (slug or id, C5): ``AmendmentsPage`` passes a slug,
    ``FinalizeResolution`` passes the numeric ``resolutionId``.
    """

    async def execute(self, session: AsyncSession, param: str) -> dict:
        resolution = await self._resolve_parent(session, param)
        amendments = await self._amendments.list_by_resolution(session, resolution.id)
        info = await self._sessions.get(session, resolution.sessionId)
        return {
            "resolution": _resolution_ref(resolution),
            "session": _session_block(info),
            "amendments": [amendment_dict(a) for a in amendments],
        }


class CreateAmendmentUseCase(_AmendmentUseCase):
    """Persist a new amendment under a resolution (spec #24): ``{success, amendment}``.

    Resolves the parent (404 when missing), then server-assigns ``resolutionId`` (from the parent),
    ``createdAt`` (today) and ``id``. Identity/author come from the body (``authorId``, C2).
    """

    async def execute(
        self, session: AsyncSession, param: str, body: AmendmentCreateBody
    ) -> dict:
        resolution = await self._resolve_parent(session, param)
        amendment = Amendment(
            **body.as_amendment_kwargs(),
            resolutionId=resolution.id,
            createdAt=_today(),
        )
        created = await self._amendments.add(session, amendment)
        return {"success": True, "amendment": amendment_dict(created)}


class GetAmendmentUnderResolutionUseCase(_AmendmentUseCase):
    """One amendment under a resolution (spec #25): ``{resolution, amendment, session}``.

    404 ``Nie znaleziono poprawki`` when the amendment is missing or does not belong to the parent.
    """

    async def execute(
        self, session: AsyncSession, param: str, amendment_id: int
    ) -> dict:
        resolution = await self._resolve_parent(session, param)
        amendment = await self._amendments.get_by_id(session, amendment_id)
        if amendment is None or amendment.resolutionId != resolution.id:
            raise NotFoundError(_AMENDMENT_NOT_FOUND)
        info = await self._sessions.get(session, resolution.sessionId)
        return {
            "resolution": _resolution_ref(resolution),
            "amendment": amendment_dict(amendment),
            "session": _session_block(info),
        }


class ListAmendmentsUseCase(_AmendmentUseCase):
    """All amendments as a **bare array** with conflicts computed (spec #26, C10)."""

    async def execute(self, session: AsyncSession) -> list[dict]:
        from mparlament.slices.amendments.domain.services import detect_all_conflicts

        amendments = await self._amendments.list_all(session)
        return detect_all_conflicts(amendments)


class GetAmendmentUseCase(_AmendmentUseCase):
    """One amendment wrapped for the voting linked-item read (spec #27, C10)."""

    async def execute(self, session: AsyncSession, amendment_id: int) -> dict:
        from mparlament.slices.amendments.domain.services import detect_all_conflicts

        amendment = await self._amendments.get_by_id(session, amendment_id)
        if amendment is None:
            raise NotFoundError(_AMENDMENT_NOT_FOUND)
        siblings = await self._amendments.list_by_resolution(
            session, amendment.resolutionId
        )
        with_conflicts = detect_all_conflicts(siblings)
        result = next((a for a in with_conflicts if a["id"] == amendment_id), None)
        if result is None:
            raise NotFoundError(_AMENDMENT_NOT_FOUND)

        resolution = None
        if amendment.resolutionId is not None:
            resolution = await self._resolutions.get_by_id(
                session, amendment.resolutionId
            )
        result["resolution"] = (
            {
                "id": resolution.id,
                "title": resolution.title,
                "slug": resolution.slug,
            }
            if resolution
            else None
        )
        return {"data": result}


class WithdrawAmendmentUseCase(_AmendmentUseCase):
    """Author-only withdraw (spec #28): 404 (missing) / 400 (already withdrawn) / 403 (not author).

    Identity (``actor_id``) is resolved in the router via the C2 chain; the author check and the
    already-withdrawn conflict live in the domain (``Amendment.withdraw``).
    """

    async def execute(
        self,
        session: AsyncSession,
        amendment_id: int,
        actor_id: int | None,
        reason: str | None,
    ) -> dict:
        amendment = await self._amendments.get_by_id(session, amendment_id)
        if amendment is None:
            raise NotFoundError(_AMENDMENT_NOT_FOUND)
        amendment.withdraw(actor_id, reason)
        updated = await self._amendments.update(session, amendment)
        return {"success": True, "amendment": amendment_dict(updated)}
