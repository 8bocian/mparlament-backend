"""SQLAlchemy models for the resolutions slice.

- ``resolutions`` — scalar columns plus a JSON ``chapters`` column (document-shaped; matches the
  FE's reads/writes and avoids over-normalizing chapters/articles — KISS/YAGNI). ``slug`` carries a
  unique index (C12). ``signatures`` keeps the FE-facing scalar count in sync with the rows.
- ``resolution_signatures`` — one row per signature with a **unique (resolution_id, user_id)**
  constraint enforcing the single-signature rule at the DB level (the application check is the fast
  path; this is the backstop). ``type`` ∈ {author, signature}.

Registered on ``Base.metadata`` via ``shared.models_registry`` so create_all/Alembic see them.
"""

from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mparlament.shared.db import Base


class ResolutionModel(Base):
    __tablename__ = "resolutions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, default="")
    slug: Mapped[str] = mapped_column(String, unique=True, index=True)
    file_name: Mapped[str | None] = mapped_column(String, nullable=True)
    author_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    author: Mapped[str] = mapped_column(String, default="")
    party: Mapped[str | None] = mapped_column(String, nullable=True)
    session_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    preamble: Mapped[str | None] = mapped_column(String, nullable=True)
    chapters: Mapped[list] = mapped_column(JSON, default=list)
    signatures: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="pending")
    created_at: Mapped[str | None] = mapped_column(String, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String, nullable=True)


class ResolutionSignatureModel(Base):
    __tablename__ = "resolution_signatures"
    __table_args__ = (
        UniqueConstraint(
            "resolution_id", "user_id", name="uq_resolution_signatures_resolution_user"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resolution_id: Mapped[int] = mapped_column(
        ForeignKey("resolutions.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    timestamp: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String, default="signature")
