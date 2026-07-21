"""Dev seed for the votings slice (spec §2 / doc 05).

Inserts a few votings across statuses (active / upcoming / archived), one linked to a resolution
by id (loose coupling — the resolutions slice need not exist). Idempotent: skips anything already
present so it is safe at startup and in tests. Does not commit.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.slices.votings.infrastructure.models import VotingModel

DEV_VOTINGS: list[dict] = [
    {
        "id": 1,
        "title": "Głosowanie nad uchwałą klimatyczną",
        "description": "Przyjęcie uchwały w sprawie polityki klimatycznej.",
        "category": "resolution",
        "start_time": "2026-09-19T12:00:00",
        "end_time": "2026-09-19T12:30:00",
        "status": "active",
        "recipients_type": "all",
        "selected_groups": [],
        "selected_members": [],
        "linked_item_type": "resolution",
        "linked_item_id": "1",
        "applicant": "marshal",
        "managers": [3],
        "attachments": [],
        "created_by": "Jan Kowalski",
        "options": {},
    },
    {
        "id": 2,
        "title": "Głosowanie budżetowe",
        "description": "Zatwierdzenie budżetu na kolejny rok.",
        "category": "budget",
        "start_time": "2026-09-19T14:00:00",
        "end_time": "2026-09-19T14:30:00",
        "status": "upcoming",
        "recipients_type": "groups",
        "selected_groups": ["A", "B"],
        "selected_members": [],
        "linked_item_type": "none",
        "linked_item_id": None,
        "applicant": "presidium",
        "managers": [],
        "attachments": [],
        "created_by": "Jan Kowalski",
        "options": {},
    },
    {
        "id": 3,
        "title": "Głosowanie proceduralne (zakończone)",
        "description": "Zamknięte głosowanie proceduralne.",
        "category": "committee",
        "start_time": "2026-09-18T10:00:00",
        "end_time": "2026-09-18T10:15:00",
        "status": "archived",
        "recipients_type": "members",
        "selected_groups": [],
        "selected_members": [2, 3],
        "linked_item_type": "none",
        "linked_item_id": None,
        "applicant": "group_15",
        "managers": [],
        "attachments": [],
        "created_by": "Jan Kowalski",
        "options": {},
    },
]


async def seed_votings(session: AsyncSession) -> None:
    """Insert any missing ``DEV_VOTINGS``. Does not commit."""
    existing = set((await session.execute(select(VotingModel.id))).scalars().all())
    for spec in DEV_VOTINGS:
        if spec["id"] in existing:
            continue
        session.add(VotingModel(**spec))
    await session.flush()
