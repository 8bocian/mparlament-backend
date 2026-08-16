"""Dev seed for the amendments slice (spec §2 / doc 07).

Inserts a couple of amendments on seeded resolution 1 with a mix of ``modify``/``add``/``delete``
changes; one stays ``pending``. Idempotent: skips anything already present so it is safe at startup
and in tests. Does not commit. Depends on ``seed_resolutions`` (parent) + ``seed_users`` (authors).
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.slices.amendments.infrastructure.models import AmendmentModel

DEV_AMENDMENTS: list[dict] = [
    {
        "id": 1,
        "resolution_id": 1,
        "author": "Anna Nowak",
        "author_id": 2,
        "club": "KO",
        "content": "Doprecyzowanie celów i dodanie artykułu o finansowaniu.",
        "status": "pending",
        "created_at": "2026-07-10",
        "withdrawn_reason": None,
        "changes": [
            {
                "articleId": 1,
                "type": "modify",
                "before": "Ustala się cele polityki klimatycznej.",
                "after": "Ustala się mierzalne cele polityki klimatycznej do 2030 roku.",
            },
            {
                "articleId": "new_1720598400000",
                "type": "add",
                "before": "",
                "after": "Źródła finansowania działań określa odrębna uchwała budżetowa.",
            },
        ],
    },
    {
        "id": 2,
        "resolution_id": 1,
        "author": "Piotr Wiśniewski",
        "author_id": 3,
        "club": "PiS",
        "content": "Wykreślenie artykułu o harmonogramie.",
        "status": "pending",
        "created_at": "2026-07-11",
        "withdrawn_reason": None,
        "changes": [
            {
                "articleId": 3,
                "type": "delete",
                "before": "Harmonogram działań na lata 2026-2030.",
                "after": "",
            },
        ],
    },
]


async def seed_amendments(session: AsyncSession) -> None:
    """Insert any missing ``DEV_AMENDMENTS``. Does not commit."""
    existing = set(
        (await session.execute(select(AmendmentModel.id))).scalars().all()
    )
    for spec in DEV_AMENDMENTS:
        if spec["id"] in existing:
            continue
        session.add(AmendmentModel(**spec))
    await session.flush()
