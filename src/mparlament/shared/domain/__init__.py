"""Shared domain kernel: base entities and the domain error hierarchy."""

from __future__ import annotations

from mparlament.shared.domain.base import AggregateRoot, Entity
from mparlament.shared.domain.errors import (
    ConflictError,
    DomainError,
    NotFoundError,
    PermissionDeniedError,
    UnauthorizedError,
    ValidationError,
)

__all__ = [
    "AggregateRoot",
    "ConflictError",
    "DomainError",
    "Entity",
    "NotFoundError",
    "PermissionDeniedError",
    "UnauthorizedError",
    "ValidationError",
]
