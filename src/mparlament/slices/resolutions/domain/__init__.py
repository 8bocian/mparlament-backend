"""Resolutions-slice domain layer (framework-free)."""

from __future__ import annotations

from mparlament.slices.resolutions.domain.entities import (
    AUTHOR,
    SIGNATURE,
    Article,
    Chapter,
    Resolution,
    ResolutionSignature,
    slugify,
)
from mparlament.slices.resolutions.domain.ports import (
    DirectoryUser,
    ResolutionRepository,
    SessionInfo,
    SessionLookup,
    SignatureRepository,
    UserDirectory,
)
from mparlament.slices.resolutions.domain.services import resolve_resolution

__all__ = [
    "AUTHOR",
    "SIGNATURE",
    "Article",
    "Chapter",
    "DirectoryUser",
    "Resolution",
    "ResolutionRepository",
    "ResolutionSignature",
    "SessionInfo",
    "SessionLookup",
    "SignatureRepository",
    "UserDirectory",
    "resolve_resolution",
    "slugify",
]
