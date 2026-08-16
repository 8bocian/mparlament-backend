"""Amendments-slice domain (framework-free) — spec §2 (Amendment), §4 (AMENDMENTS).

- ``Amendment`` — the poprawka aggregate. Carries the persisted fields the FE reads/writes
  (spec §2 Amendment). ``changes`` is a document-shaped list of ``Change`` value objects (stored
  as JSON on the row — KISS/YAGNI, matches the FE's article-diff reads/writes). ``createdAt`` is a
  verbatim FE-format date string ``YYYY-MM-DD`` (C13); the domain never parses it.
- ``Change`` — one article diff ``{articleId, before, after, type?}``. Value-conventions (spec §2):
  ``before=null/""`` → new article (``add``); ``after="(usunięty)"``/``""`` → deletion
  (``delete``); ``add`` uses ``articleId="new_<timestamp>"``. The domain stores the shape as-is —
  it does not rewrite the convention values (the FE authored them).

Domain behaviour: only the author may ``withdraw`` their amendment (author-only, C3); withdrawing
an already-withdrawn amendment is a conflict (C11). Statuses: pending|accepted|rejected|withdrawn.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mparlament.shared.domain import ConflictError, PermissionDeniedError

PENDING = "pending"
ACCEPTED = "accepted"
REJECTED = "rejected"
WITHDRAWN = "withdrawn"

_NOT_AUTHOR = "Brak uprawnień"
_ALREADY_WITHDRAWN = "Poprawka została już wycofana"
_DEFAULT_REASON = "Brak podanego powodu"


# --- value object ----------------------------------------------------------


@dataclass(frozen=True)
class Change:
    """A single article diff within an amendment (spec §2 Amendment.changes[]).

    ``type`` ∈ {modify, add, delete} and is optional (the FE may omit it). Convention values
    (``before=""`` for add, ``after="(usunięty)"``/``""`` for delete) are stored verbatim.
    """

    articleId: str | int | None = None
    before: str = ""
    after: str = ""
    type: str | None = None


def _to_change(value: object) -> Change:
    if isinstance(value, Change):
        return value
    data = dict(value)  # type: ignore[arg-type]
    return Change(
        articleId=data.get("articleId"),
        before=data.get("before", "") or "",
        after=data.get("after", "") or "",
        type=data.get("type"),
    )


# --- entity ----------------------------------------------------------------


@dataclass
class Amendment:
    """The poprawka aggregate (spec §2 Amendment)."""

    id: int | None = None
    resolutionId: int | None = None
    author: str = ""
    authorId: int | None = None
    club: str | None = None
    content: str = ""
    status: str = PENDING  # pending|accepted|rejected|withdrawn
    createdAt: str | None = None  # "YYYY-MM-DD" (C13)
    withdrawnReason: str | None = None
    changes: list = field(default_factory=list)

    def __post_init__(self) -> None:
        self.changes = [_to_change(c) for c in self.changes]

    def is_author(self, user_id: int | None) -> bool:
        return user_id is not None and self.authorId == user_id

    def withdraw(self, actor_id: int | None, reason: str | None) -> None:
        """Withdraw this amendment (spec #28): author-only, once.

        Raises ``PermissionDeniedError`` (403) when ``actor_id`` is not the author, and
        ``ConflictError`` (400) when the amendment is already withdrawn. On success sets
        ``status="withdrawn"`` and records ``withdrawnReason`` (default when none given, C11).
        """
        if not self.is_author(actor_id):
            raise PermissionDeniedError(_NOT_AUTHOR)
        if self.status == WITHDRAWN:
            raise ConflictError(_ALREADY_WITHDRAWN)
        self.status = WITHDRAWN
        self.withdrawnReason = reason or _DEFAULT_REASON
