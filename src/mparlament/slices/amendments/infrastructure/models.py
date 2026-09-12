"""SQLAlchemy model for the amendments slice.

``amendments`` — scalar columns plus a JSON ``changes`` column (document-shaped article diffs;
matches the FE's reads/writes and avoids over-normalizing changes — KISS/YAGNI). ``resolution_id``
is a FK to ``resolutions.id`` (cascade delete: an amendment cannot outlive its parent uchwała).
``created_at`` is a date string ``YYYY-MM-DD`` (C13).

Registered on ``Base.metadata`` via ``shared.models_registry`` so create_all/Alembic see it.
"""

from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from mparlament.shared.db import Base


class AmendmentModel(Base):
    __tablename__ = "amendments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resolution_id: Mapped[int] = mapped_column(
        ForeignKey("resolutions.id", ondelete="CASCADE"), index=True
    )
    author: Mapped[str] = mapped_column(String, default="")
    author_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    club: Mapped[str | None] = mapped_column(String, nullable=True)
    content: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String, default="pending")
    created_at: Mapped[str | None] = mapped_column(String, nullable=True)
    withdrawn_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    changes: Mapped[list] = mapped_column(JSON, default=list)
    target: Mapped[dict | None] = mapped_column(JSON, nullable=True)
