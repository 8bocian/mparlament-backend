"""Pydantic DTOs for the resolutions slice (spec §4 #19).

Only the create payload's ``data`` JSON string is modelled here — the reads are built as plain
dicts in ``application/views.py`` (the FE tolerates extra keys, C10). ``ResolutionCreateData``
parses the ``data`` blob the FE posts as a multipart field (#19): ``editedData`` (title, chapters,
preamble?) plus fileName/author/authorId/party/sessionId.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError as PydanticValidationError

from mparlament.shared.domain import ValidationError
from mparlament.slices.resolutions.domain.entities import Article, Chapter


class ArticleInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | int | None = None
    number: str | int | None = None
    content: str = ""


class ChapterInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | int | None = None
    title: str = ""
    articles: list[ArticleInput] = []


class ResolutionCreateData(BaseModel):
    """The parsed ``data`` JSON-string body of ``POST /api/resolutions`` (#19)."""

    model_config = ConfigDict(extra="ignore")

    title: str = ""
    fileName: str | None = None
    author: str = ""
    authorId: int | None = None
    party: str | None = None
    sessionId: int | None = None
    preamble: str | None = None
    chapters: list[ChapterInput] = []

    @classmethod
    def parse(cls, raw: str | bytes | None) -> "ResolutionCreateData":
        """Parse the multipart ``data`` field (a JSON string) → validated DTO (422 on bad JSON)."""
        if raw is None:
            raise ValidationError("Brak danych uchwały")
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ValidationError("Nieprawidłowe dane uchwały") from exc
        try:
            return cls.model_validate(payload)
        except PydanticValidationError as exc:  # pragma: no cover - defensive
            raise ValidationError("Nieprawidłowe dane uchwały") from exc

    def chapters_domain(self) -> list[Chapter]:
        return [
            Chapter(
                id=c.id,
                title=c.title,
                articles=[
                    Article(id=a.id, number=a.number, content=a.content)
                    for a in c.articles
                ],
            )
            for c in self.chapters
        ]

    def as_kwargs(self) -> dict[str, Any]:
        """The Resolution constructor kwargs carried by this payload (slug/status set by the UC)."""
        return {
            "title": self.title,
            "fileName": self.fileName,
            "authorId": self.authorId,
            "author": self.author,
            "party": self.party,
            "sessionId": self.sessionId,
            "preamble": self.preamble,
            "chapters": self.chapters_domain(),
        }
