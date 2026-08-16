"""Read-time projections of resolutions into the FE-facing shapes (spec §2, §4, C10).

- ``resolution_dict`` — the bare ``Resolution`` object (with ``chapters``) the FE reads on list,
  create and detail responses.
- ``signed_user`` — a signature expanded to ``{name, club, timestamp, type}`` via the directory.
- ``current_user_block`` — the requester-specific ``{hasSigned, isAuthor, signatureType,
  isAutoSigned}`` block (present only when identity is known, C2/C10).
"""

from __future__ import annotations

from dataclasses import asdict

from mparlament.slices.resolutions.domain.entities import (
    AUTHOR,
    Resolution,
    ResolutionSignature,
)
from mparlament.slices.resolutions.domain.ports import DirectoryUser


def resolution_dict(resolution: Resolution) -> dict:
    """The ``Resolution`` object the FE reads (spec §2 Resolution), ``chapters`` included."""
    return {
        "id": resolution.id,
        "title": resolution.title,
        "slug": resolution.slug,
        "fileName": resolution.fileName,
        "authorId": resolution.authorId,
        "author": resolution.author,
        "party": resolution.party,
        "sessionId": resolution.sessionId,
        "preamble": resolution.preamble,
        "chapters": [asdict(c) for c in resolution.chapters],
        "signatures": resolution.signatures,
        "status": resolution.status,
        "createdAt": resolution.createdAt,
        "filePath": resolution.filePath,
    }


def signed_user(
    signature: ResolutionSignature, users_by_id: dict[int, DirectoryUser]
) -> dict:
    """Expand a signature to ``{name, club, timestamp, type}`` (spec §4 #18)."""
    user = users_by_id.get(signature.userId)
    return {
        "name": user.name if user else None,
        "club": user.club if user else None,
        "timestamp": signature.timestamp,
        "type": signature.type,
    }


def current_user_block(
    resolution: Resolution,
    signatures: list[ResolutionSignature],
    requester_id: int,
) -> dict:
    """The requester-specific signing block (spec §4 #18); keys always present once identity known."""
    mine = next((s for s in signatures if s.userId == requester_id), None)
    return {
        "hasSigned": mine is not None,
        "isAuthor": resolution.is_author(requester_id),
        "signatureType": mine.type if mine else None,
        "isAutoSigned": bool(mine and mine.type == AUTHOR),
    }
