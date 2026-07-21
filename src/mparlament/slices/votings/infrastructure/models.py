"""SQLAlchemy models for the votings slice.

- ``votings`` — scalar columns plus JSON columns for the list/document-shaped fields
  (``selected_groups``, ``selected_members``, ``managers``, ``attachments``, ``options``). JSON
  avoids premature normalization (YAGNI) while matching the FE's document reads/writes.
  ``linked_item_id`` is stored as a string (polymorphic — uchwała/poprawka po ID).
- ``votes`` — one row per cast vote with a **unique (voting_id, user_id)** constraint enforcing the
  single-vote rule at the DB level (the application check is the fast path; this is the backstop).

Registered on ``Base.metadata`` via ``shared.models_registry`` so create_all/Alembic see them.
"""

from __future__ import annotations

from sqlalchemy import JSON, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from mparlament.shared.db import Base


class VotingModel(Base):
    __tablename__ = "votings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String, default="")
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    category: Mapped[str] = mapped_column(String, default="other")
    start_time: Mapped[str | None] = mapped_column(String, nullable=True)
    end_time: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="upcoming")
    recipients_type: Mapped[str] = mapped_column(String, default="all")
    selected_groups: Mapped[list] = mapped_column(JSON, default=list)
    selected_members: Mapped[list] = mapped_column(JSON, default=list)
    linked_item_type: Mapped[str] = mapped_column(String, default="none")
    linked_item_id: Mapped[str | None] = mapped_column(String, nullable=True)
    applicant: Mapped[str | None] = mapped_column(String, nullable=True)
    managers: Mapped[list] = mapped_column(JSON, default=list)
    attachments: Mapped[list] = mapped_column(JSON, default=list)
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    options: Mapped[dict] = mapped_column(JSON, default=dict)


class VoteModel(Base):
    __tablename__ = "votes"
    __table_args__ = (
        UniqueConstraint("voting_id", "user_id", name="uq_votes_voting_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    voting_id: Mapped[int] = mapped_column(
        ForeignKey("votings.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    value: Mapped[str] = mapped_column(String)
