"""Idempotent dev seed (spec §7 / doc 00 §7).

Slice 00 owns only the runner: it ensures the schema exists and invokes each slice's seed
hook. Slices register their seed data by appending a callable to ``SEED_HOOKS`` as they are
built (e.g. auth_identity seeds the ``TEST123`` admin, votings seed 2-3 demo votings). Each
hook must be idempotent (upsert by natural key) so re-running ``python scripts/seed.py`` is
safe.

Run with:  ``python scripts/seed.py``
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.shared.db import Base, async_session_factory, engine
import mparlament.shared.models_registry  # noqa: F401  (registers all ORM models)
from mparlament.slices.amendments.infrastructure.seed import seed_amendments
from mparlament.slices.auth_identity.infrastructure.seed import seed_users
from mparlament.slices.parliamentarians_clubs.infrastructure.seed import (
    seed_parliamentarians_clubs,
)
from mparlament.slices.resolutions.infrastructure.seed import seed_resolutions
from mparlament.slices.sessions.infrastructure.seed import seed_sessions
from mparlament.slices.votings.infrastructure.seed import seed_votings

SeedHook = Callable[[AsyncSession], Awaitable[None]]

# Idempotent slice seed hooks, ordered by data dependency: users first (authors/voters), then
# sessions (referenced by resolutions), the independent parliamentarian registry, then
# resolutions → amendments (child) → votings (links resolutions/amendments by id).
SEED_HOOKS: list[SeedHook] = [
    seed_users,
    seed_sessions,
    seed_parliamentarians_clubs,
    seed_resolutions,
    seed_amendments,
    seed_votings,
]


async def _ensure_schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def seed() -> None:
    await _ensure_schema()
    async with async_session_factory() as session:
        for hook in SEED_HOOKS:
            await hook(session)
        await session.commit()


def main() -> None:
    asyncio.run(seed())
    print(f"Seed complete ({len(SEED_HOOKS)} slice hook(s)).")


if __name__ == "__main__":
    main()
