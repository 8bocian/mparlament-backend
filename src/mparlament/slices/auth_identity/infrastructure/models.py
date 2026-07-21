"""SQLAlchemy model for the ``users`` table (spec §2 User).

``permissions`` is stored as JSON (SQLite ``JSON`` type). ``username`` is uniquely indexed.
Registered on ``Base.metadata`` via ``shared.models_registry`` so create_all/Alembic see it.
"""

from __future__ import annotations

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from mparlament.shared.db import Base


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String, default="")
    club: Mapped[str | None] = mapped_column(String, nullable=True)
    role: Mapped[str] = mapped_column(String, default="member")
    permissions: Mapped[list[str]] = mapped_column(JSON, default=list)
    group: Mapped[str | None] = mapped_column(String, nullable=True)
