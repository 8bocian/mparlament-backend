"""Mappers between the resolutions ORM rows and the framework-free domain objects.

``chapters`` round-trip through the frozen ``Chapter``/``Article`` value objects; ``apply_resolution``
writes them back as plain JSON (``dataclasses.asdict``) so SQLite's ``JSON`` type can store them.
"""

from __future__ import annotations

from dataclasses import asdict

from mparlament.slices.resolutions.domain.entities import (
    Resolution,
    ResolutionSignature,
)
from mparlament.slices.resolutions.infrastructure.models import (
    ResolutionModel,
    ResolutionSignatureModel,
)


def to_resolution(row: ResolutionModel) -> Resolution:
    return Resolution(
        id=row.id,
        title=row.title,
        slug=row.slug,
        fileName=row.file_name,
        authorId=row.author_id,
        author=row.author,
        party=row.party,
        sessionId=row.session_id,
        preamble=row.preamble,
        chapters=list(row.chapters or []),
        signatures=row.signatures,
        status=row.status,
        createdAt=row.created_at,
        filePath=row.file_path,
    )


def apply_resolution(row: ResolutionModel, resolution: Resolution) -> None:
    """Copy a domain ``Resolution`` onto an ORM row (``chapters`` as plain JSON)."""
    row.title = resolution.title
    row.slug = resolution.slug
    row.file_name = resolution.fileName
    row.author_id = resolution.authorId
    row.author = resolution.author
    row.party = resolution.party
    row.session_id = resolution.sessionId
    row.preamble = resolution.preamble
    row.chapters = [asdict(c) for c in resolution.chapters]
    row.signatures = resolution.signatures
    row.status = resolution.status
    row.created_at = resolution.createdAt
    row.file_path = resolution.filePath


def to_signature(row: ResolutionSignatureModel) -> ResolutionSignature:
    return ResolutionSignature(
        id=row.id,
        resolutionId=row.resolution_id,
        userId=row.user_id,
        timestamp=row.timestamp,
        type=row.type,
    )
