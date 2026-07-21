"""Domain error hierarchy with HTTP-mapping hints.

Each subtype carries a ``.message`` (a Polish string from CONVENTIONS C11) and a
``.status_code``. ``shared.api.exceptions`` turns any :class:`DomainError` into a JSON
``{"message": ...}`` response with that status, so slices raise these instead of importing
FastAPI's ``HTTPException`` into their domain/application layers.
"""

from __future__ import annotations


class DomainError(Exception):
    """Base domain error. Maps to HTTP 400 unless a subtype overrides ``status_code``."""

    status_code: int = 400

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class NotFoundError(DomainError):
    """Requested aggregate does not exist -> 404."""

    status_code = 404


class ConflictError(DomainError):
    """Invariant/state conflict, e.g. already voted / already signed -> 400."""

    status_code = 400


class PermissionDeniedError(DomainError):
    """Authenticated but not allowed -> 403."""

    status_code = 403


class UnauthorizedError(DomainError):
    """No/!invalid identity where one is required -> 401."""

    status_code = 401


class ValidationError(DomainError):
    """Semantically invalid input -> 422."""

    status_code = 422
