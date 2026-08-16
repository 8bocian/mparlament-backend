"""Resolutions-slice domain (framework-free) — spec §2 (Resolution, ResolutionSignature), §4.

Two aggregates plus document-shaped value objects and the pure services the slice needs:

- ``Resolution`` — the uchwała aggregate. Carries the persisted fields the FE reads/writes
  (spec §2 Resolution). ``chapters`` is a document-shaped list of ``Chapter``/``Article`` value
  objects (stored as JSON on the row — KISS/YAGNI, matches the FE's document reads/writes). Dates
  are verbatim FE-format strings (``createdAt`` is ``YYYY-MM-DD``, C13); the domain never parses.
- ``ResolutionSignature`` — a single signature ``{id, resolutionId, userId, timestamp, type}``.
  The author is auto-signed on create (``type="author"``) and cannot remove their signature
  (``ensure_removable`` guards this, C11); every other signer is ``type="signature"``.

``slugify`` is the single source of truth for slug generation (C12): lowercase, spaces → ``-``,
strip characters outside ``[\\w-]`` (Polish word chars survive), collision → ``-2``, ``-3``, ….
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from mparlament.shared.domain import PermissionDeniedError

AUTHOR = "author"
SIGNATURE = "signature"

_AUTHOR_CANNOT_UNSIGN = "Autor nie może usunąć podpisu"


# --- slug generation (C12) -------------------------------------------------


def slugify(title: str, taken: Iterable[str] = ()) -> str:
    """Slug per C12: lowercase, spaces → ``-``, drop non-``[\\w-]``; collision → ``-2``, ``-3``, ….

    ``\\w`` is unicode-aware, so Polish letters (ą, ł, ż…) are preserved. ``taken`` is the set of
    slugs already in use; the returned slug is guaranteed not to collide with it.
    """
    base = title.strip().lower()
    base = re.sub(r"\s+", "-", base)
    base = re.sub(r"[^\w-]", "", base)
    base = re.sub(r"-{2,}", "-", base).strip("-") or "uchwala"

    taken_set = set(taken)
    if base not in taken_set:
        return base
    n = 2
    while f"{base}-{n}" in taken_set:
        n += 1
    return f"{base}-{n}"


# --- value objects ---------------------------------------------------------


@dataclass(frozen=True)
class Article:
    """A single article within a chapter (spec §2 Resolution.chapters[].articles[])."""

    id: str | int | None = None
    number: str | int | None = None
    content: str = ""


@dataclass(frozen=True)
class Chapter:
    """A chapter grouping articles (spec §2 Resolution.chapters[])."""

    id: str | int | None = None
    title: str = ""
    articles: list[Article] = field(default_factory=list)


def _to_article(value: object) -> Article:
    if isinstance(value, Article):
        return value
    return Article(**dict(value))  # type: ignore[arg-type]


def _to_chapter(value: object) -> Chapter:
    if isinstance(value, Chapter):
        return value
    data = dict(value)  # type: ignore[arg-type]
    articles = [_to_article(a) for a in (data.get("articles") or [])]
    return Chapter(id=data.get("id"), title=data.get("title", ""), articles=articles)


# --- entities --------------------------------------------------------------


@dataclass
class Resolution:
    """The uchwała aggregate (spec §2 Resolution). Statuses: pending|accepted|rejected."""

    id: int | None = None
    title: str = ""
    slug: str = ""
    fileName: str | None = None
    authorId: int | None = None
    author: str = ""
    party: str | None = None
    sessionId: int | None = None
    preamble: str | None = None
    chapters: list = field(default_factory=list)
    signatures: int = 0
    status: str = "pending"  # pending|accepted|rejected
    createdAt: str | None = None  # "YYYY-MM-DD" (C13)
    filePath: str | None = None

    def __post_init__(self) -> None:
        self.chapters = [_to_chapter(c) for c in self.chapters]

    def is_author(self, user_id: int | None) -> bool:
        return user_id is not None and self.authorId == user_id


@dataclass
class ResolutionSignature:
    """A single signature row (spec §2 ResolutionSignature). ``type`` ∈ {author, signature}."""

    resolutionId: int
    userId: int
    timestamp: str
    type: str = SIGNATURE
    id: int | None = None

    def ensure_removable(self) -> None:
        """Author-protection (C11): the auto author-signature cannot be removed → 403."""
        if self.type == AUTHOR:
            raise PermissionDeniedError(_AUTHOR_CANNOT_UNSIGN)
