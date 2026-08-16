"""Read-time projection of an ``Amendment`` into the FE-facing shape (spec §2, §4, C10).

``amendment_dict`` is the bare ``Amendment`` object the FE reads everywhere (list, detail, create
and withdraw responses). ``changes`` is emitted as plain dicts; a ``Change`` with ``type=None``
still carries the key (the FE tolerates a null ``type``).
"""

from __future__ import annotations

from dataclasses import asdict

from mparlament.slices.amendments.domain.entities import Amendment


def amendment_dict(amendment: Amendment) -> dict:
    """The ``Amendment`` object the FE reads (spec §2 Amendment), ``changes`` included."""
    return {
        "id": amendment.id,
        "resolutionId": amendment.resolutionId,
        "author": amendment.author,
        "authorId": amendment.authorId,
        "club": amendment.club,
        "content": amendment.content,
        "status": amendment.status,
        "createdAt": amendment.createdAt,
        "withdrawnReason": amendment.withdrawnReason,
        "changes": [asdict(c) for c in amendment.changes],
    }
