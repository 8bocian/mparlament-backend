"""SQLAlchemy models for the parliamentarians & clubs slice (doc 08).

- ``clubs`` — ``{id, name, type, color}``. Members are **not** stored on the club (spec §6.1.7);
  they are derived from parliamentarians.
- ``parliamentarians`` — ``{id, first_name, last_name, club_id FK nullable, functions JSON,
  commissions JSON}``. ``club_id`` references ``clubs.id`` with ``ondelete=SET NULL`` so a DB-level
  club delete unlinks members; the repository also unlinks explicitly to stay DB-agnostic (#36).

Registered on ``Base.metadata`` via ``shared.models_registry`` so create_all/Alembic see them.
"""

from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from mparlament.shared.db import Base


class ClubModel(Base):
    __tablename__ = "clubs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, default="")
    type: Mapped[str] = mapped_column(String, default="klub")
    color: Mapped[str] = mapped_column(String, default="")


class ParliamentarianModel(Base):
    __tablename__ = "parliamentarians"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_name: Mapped[str] = mapped_column(String, default="")
    last_name: Mapped[str] = mapped_column(String, default="")
    club_id: Mapped[int | None] = mapped_column(
        ForeignKey("clubs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    functions: Mapped[list] = mapped_column(JSON, default=list)
    commissions: Mapped[list] = mapped_column(JSON, default=list)
