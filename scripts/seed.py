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

SeedHook = Callable[[AsyncSession], Awaitable[None]]

# Slices append their idempotent seed functions here as they are implemented.
SEED_HOOKS: list[SeedHook] = []


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
