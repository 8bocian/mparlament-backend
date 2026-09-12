"""HTTP exception handlers mapping domain errors to the FE-expected ``{message}`` shape.

Every :class:`DomainError` becomes ``{"message": err.message}`` with ``err.status_code``.
FastAPI's request-validation errors are also reduced to a ``{"message": ...}`` body (the FE
only ever reads ``data.message``). Registered once in the app factory.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from mparlament.shared.domain import DomainError


async def _domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
    body: dict = {"message": exc.message}
    payload = getattr(exc, "payload", None)
    if payload:
        body.update(payload)
    return JSONResponse(status_code=exc.status_code, content=body)


async def _validation_error_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    errors = exc.errors()
    message = (
        errors[0].get("msg", "Nieprawidłowe dane") if errors else "Nieprawidłowe dane"
    )
    return JSONResponse(status_code=422, content={"message": message})


def register_exception_handlers(app: FastAPI) -> None:
    """Wire the domain + validation handlers onto ``app`` (called by the app factory)."""
    app.add_exception_handler(DomainError, _domain_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(
        RequestValidationError,
        _validation_error_handler,  # type: ignore[arg-type]
    )
