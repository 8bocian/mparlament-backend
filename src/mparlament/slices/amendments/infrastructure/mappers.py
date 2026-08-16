"""Mappers between the amendments ORM row and the framework-free domain object.

``changes`` round-trip through the frozen ``Change`` value object; ``apply_amendment`` writes them
back as plain JSON (``dataclasses.asdict``) so SQLite's ``JSON`` type can store them.
"""

from __future__ import annotations

from dataclasses import asdict

from mparlament.slices.amendments.domain.entities import Amendment
from mparlament.slices.amendments.infrastructure.models import AmendmentModel


def to_amendment(row: AmendmentModel) -> Amendment:
    return Amendment(
        id=row.id,
        resolutionId=row.resolution_id,
        author=row.author,
        authorId=row.author_id,
        club=row.club,
        content=row.content,
        status=row.status,
        createdAt=row.created_at,
        withdrawnReason=row.withdrawn_reason,
        changes=list(row.changes or []),
    )


def apply_amendment(row: AmendmentModel, amendment: Amendment) -> None:
    """Copy a domain ``Amendment`` onto an ORM row (``changes`` as plain JSON)."""
    row.resolution_id = amendment.resolutionId
    row.author = amendment.author
    row.author_id = amendment.authorId
    row.club = amendment.club
    row.content = amendment.content
    row.status = amendment.status
    row.created_at = amendment.createdAt
    row.withdrawn_reason = amendment.withdrawnReason
    row.changes = [asdict(c) for c in amendment.changes]
