"""Shared domain services for the resolutions slice.

``resolve_resolution`` is the polymorphic slug-or-id lookup (C5): a numeric path segment resolves
by integer id, anything else by slug. It is deliberately a free function over the
``ResolutionRepository`` port so both the resolutions slice (#18/#18b) and the amendments slice
(#23/#23b) can reuse it without duplicating the rule.
"""

from __future__ import annotations

import re

from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.slices.resolutions.domain.entities import Resolution
from mparlament.slices.resolutions.domain.ports import ResolutionRepository

_NUMERIC = re.compile(r"^\d+$")


async def resolve_resolution(
    session: AsyncSession, param: str, repo: ResolutionRepository
) -> Resolution | None:
    """Look a resolution up by integer id when ``param`` is all-digits, else by slug (C5)."""
    if _NUMERIC.match(str(param)):
        return await repo.get_by_id(session, int(param))
    return await repo.get_by_slug(session, str(param))
