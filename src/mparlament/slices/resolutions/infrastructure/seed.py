"""Dev seed for the resolutions slice (spec §2 / doc 06).

Inserts a couple of resolutions with chapters (``status="pending"``, ``signatures=1``) and the
author's auto-signature row (``type="author"``). Idempotent: skips anything already present so it
is safe at startup and in tests. Does not commit.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.slices.resolutions.infrastructure.models import (
    ResolutionModel,
    ResolutionSignatureModel,
)

DEV_RESOLUTIONS: list[dict] = [
    {
        "id": 1,
        "title": "Uchwała w sprawie polityki klimatycznej",
        "slug": "uchwala-w-sprawie-polityki-klimatycznej",
        "file_name": "uchwala-klimatyczna.docx",
        "author_id": 1,
        "author": "Jan Kowalski",
        "party": "TEST",
        "session_id": 1,
        "preamble": "Parlament Młodych RP, mając na uwadze dobro wspólne, uchwala co następuje:",
        "chapters": [
            {
                "id": 1,
                "title": "Rozdział I — Postanowienia ogólne",
                "articles": [
                    {"id": 1, "number": "1", "content": "Ustala się cele polityki klimatycznej."},
                    {"id": 2, "number": "2", "content": "Definicje pojęć użytych w uchwale."},
                ],
            },
            {
                "id": 2,
                "title": "Rozdział II — Środki wykonawcze",
                "articles": [
                    {"id": 3, "number": "3", "content": "Harmonogram działań na lata 2026-2030."},
                ],
            },
        ],
        "signatures": 1,
        "status": "pending",
        "created_at": "2026-07-09",
        "file_path": "/uploads/resolutions/uchwala-klimatyczna.docx",
    },
    {
        "id": 2,
        "title": "Uchwała w sprawie edukacji obywatelskiej",
        "slug": "uchwala-w-sprawie-edukacji-obywatelskiej",
        "file_name": "uchwala-edukacja.docx",
        "author_id": 2,
        "author": "Anna Nowak",
        "party": "KO",
        "session_id": 1,
        "preamble": None,
        "chapters": [
            {
                "id": 1,
                "title": "Rozdział I",
                "articles": [
                    {"id": 1, "number": "1", "content": "Wprowadzenie zajęć obywatelskich."},
                ],
            },
        ],
        "signatures": 1,
        "status": "pending",
        "created_at": "2026-07-12",
        "file_path": "/uploads/resolutions/uchwala-edukacja.docx",
    },
]

# Author auto-signatures (spec §2 ResolutionSignature; type="author").
DEV_SIGNATURES: list[dict] = [
    {"resolution_id": 1, "user_id": 1, "timestamp": "2026-07-09T10:00:00+00:00", "type": "author"},
    {"resolution_id": 2, "user_id": 2, "timestamp": "2026-07-12T09:30:00+00:00", "type": "author"},
]


async def seed_resolutions(session: AsyncSession) -> None:
    """Insert any missing ``DEV_RESOLUTIONS`` + author signatures. Does not commit."""
    existing = set(
        (await session.execute(select(ResolutionModel.id))).scalars().all()
    )
    for spec in DEV_RESOLUTIONS:
        if spec["id"] in existing:
            continue
        session.add(ResolutionModel(**spec))

    existing_sigs = {
        (r_id, u_id)
        for r_id, u_id in (
            await session.execute(
                select(
                    ResolutionSignatureModel.resolution_id,
                    ResolutionSignatureModel.user_id,
                )
            )
        ).all()
    }
    for spec in DEV_SIGNATURES:
        if (spec["resolution_id"], spec["user_id"]) in existing_sigs:
            continue
        session.add(ResolutionSignatureModel(**spec))

    await session.flush()
