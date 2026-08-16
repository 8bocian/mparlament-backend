"""Pydantic DTOs for the amendments slice (spec §4 #24, #28).

- ``AmendmentCreateBody`` — the JSON body ``AddAmendment`` POSTs (#24): author/authorId/club/
  content/status/changes plus a ``resolutionId`` the server overrides with the resolved parent.
  ``changes[]`` mirrors the ``Change`` value object; convention values are carried through as-is.
- ``WithdrawBody`` — ``{reason}`` for #28 (default applied in the domain when absent).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from mparlament.slices.amendments.domain.entities import Amendment, Change


class ChangeInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    articleId: str | int | None = None
    before: str = ""
    after: str = ""
    type: str | None = None


class AmendmentCreateBody(BaseModel):
    """The JSON body of ``POST /api/resolutions/:slug/amendments`` (#24)."""

    model_config = ConfigDict(extra="ignore")

    resolutionId: int | None = None
    author: str = ""
    authorId: int | None = None
    club: str | None = None
    content: str = ""
    status: str = "pending"
    withdrawnReason: str | None = None
    changes: list[ChangeInput] = []

    def changes_domain(self) -> list[Change]:
        return [
            Change(
                articleId=c.articleId,
                before=c.before,
                after=c.after,
                type=c.type,
            )
            for c in self.changes
        ]

    def as_amendment_kwargs(self) -> dict[str, Any]:
        """Amendment constructor kwargs carried by this body (id/createdAt/resolutionId set by UC)."""
        return {
            "author": self.author,
            "authorId": self.authorId,
            "club": self.club,
            "content": self.content,
            "status": self.status or "pending",
            "withdrawnReason": self.withdrawnReason,
            "changes": self.changes_domain(),
        }


class WithdrawBody(BaseModel):
    """The JSON body of ``POST /api/amendments/:id/withdraw`` (#28)."""

    model_config = ConfigDict(extra="ignore")

    reason: str | None = None
    # Identity may also arrive in the body when the FE sends no token (C2 chain).
    authorId: int | None = None
    userId: int | None = None
