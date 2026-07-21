"""Pydantic request DTOs for the votings slice (spec §4 #10-#13).

Responses are built as plain dicts by ``application/views.py`` (the computed projection carries
many dynamic keys and the FE tolerates extras, C10) — so only *inputs* are modelled here.

``VotingWriteInput`` covers the create/update body (#10/#11): the scalar Voting fields plus the
create-form option flags, which are collected into an opaque ``options`` dict via ``to_domain``.
``VoteInput`` and ``ActivateInput`` are the small action bodies (#12/#13).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from mparlament.slices.votings.domain.entities import OPTION_KEYS, Attachment, Voting


class AttachmentInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    id: str | int | None = None
    size: int | None = None
    type: str | None = None
    uploadDate: str | None = None


class VotingWriteInput(BaseModel):
    """``POST``/``PUT`` body (spec #10/#11). Unknown option flags are captured via ``extra``."""

    model_config = ConfigDict(extra="allow")

    title: str = ""
    description: str | None = None
    category: str = "other"
    startTime: str | None = None
    endTime: str | None = None
    status: str | None = None
    recipientsType: str = "all"
    selectedGroups: list[Any] = []
    selectedMembers: list[Any] = []
    linkedItemType: str = "none"
    linkedItemId: str | int | None = None
    applicant: str | None = None
    managers: list[int] = []
    attachments: list[AttachmentInput] = []
    createdBy: str | None = None

    def to_domain(self, *, voting_id: int | None = None) -> Voting:
        """Build the domain ``Voting`` (option flags gathered into ``options``, C15 default status)."""
        extra = self.model_extra or {}
        options = {key: extra[key] for key in OPTION_KEYS if key in extra}
        return Voting(
            id=voting_id,
            title=self.title,
            description=self.description,
            category=self.category,
            startTime=self.startTime,
            endTime=self.endTime,
            status=self.status or "upcoming",
            recipientsType=self.recipientsType,
            selectedGroups=list(self.selectedGroups),
            selectedMembers=[int(m) for m in self.selectedMembers],
            linkedItemType=self.linkedItemType,
            linkedItemId=self.linkedItemId,
            applicant=self.applicant,
            managers=[int(m) for m in self.managers],
            attachments=[Attachment(**a.model_dump()) for a in self.attachments],
            createdBy=self.createdBy,
            options=options,
        )


class VoteInput(BaseModel):
    """``POST /api/votings/:id/vote`` body (spec #12)."""

    model_config = ConfigDict(extra="ignore")

    vote: str


class ActivateInput(BaseModel):
    """``POST /api/votings/:id/activate`` body (spec #13)."""

    model_config = ConfigDict(extra="ignore")

    startTime: str | None = None
    endTime: str | None = None
    duration: Any | None = None
    delay: Any | None = None
