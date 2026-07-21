"""Dev seed users (spec §2 / doc 02: an admin ``TEST123`` plus a couple of members).

Idempotent: skips a username that already exists so it is safe to call at startup and in tests.
Plaintext passwords live here only for local development; ``password_hash`` is what is stored.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mparlament.slices.auth_identity.infrastructure.models import UserModel
from mparlament.slices.auth_identity.infrastructure.password_hasher import (
    BcryptPasswordHasher,
)

DEV_USERS: list[dict] = [
    {
        "username": "TEST123",
        "password": "test123",
        "name": "Jan Kowalski",
        "role": "admin",
        "permissions": [],
        "club": "TEST",
        "group": None,
    },
    {
        "username": "MEMBER1",
        "password": "member1",
        "name": "Anna Nowak",
        "role": "member",
        "permissions": [],
        "club": "KO",
        "group": "A",
    },
    {
        "username": "MEMBER2",
        "password": "member2",
        "name": "Piotr Wiśniewski",
        "role": "member",
        "permissions": ["MANAGE_VOTINGS"],
        "club": "PiS",
        "group": "B",
    },
]


async def seed_users(session: AsyncSession) -> None:
    """Insert any missing ``DEV_USERS`` (bcrypt-hashed). Does not commit."""
    hasher = BcryptPasswordHasher()
    existing = set(
        (await session.execute(select(UserModel.username))).scalars().all()
    )
    for spec in DEV_USERS:
        if spec["username"] in existing:
            continue
        session.add(
            UserModel(
                username=spec["username"],
                password_hash=hasher.hash(spec["password"]),
                name=spec["name"],
                club=spec["club"],
                role=spec["role"],
                permissions=list(spec["permissions"]),
                group=spec["group"],
            )
        )
    await session.flush()
