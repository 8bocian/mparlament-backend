"""Slice 01 — shared domain base classes + error mapping (TDD checklist #10)."""

from __future__ import annotations

from dataclasses import dataclass

from mparlament.shared.domain import (
    AggregateRoot,
    ConflictError,
    DomainError,
    Entity,
    NotFoundError,
    PermissionDeniedError,
    UnauthorizedError,
    ValidationError,
)


@dataclass(eq=False)
class _Thing(Entity):
    pass


@dataclass(eq=False)
class _Other(Entity):
    pass


def test_entity_equality_by_type_and_id() -> None:
    assert _Thing(id=1) == _Thing(id=1)
    assert _Thing(id=1) != _Thing(id=2)
    # Same id, different concrete type -> not equal.
    assert _Thing(id=1) != _Other(id=1)


def test_entity_without_id_is_identity_equal() -> None:
    a = _Thing()
    b = _Thing()
    assert a == a
    assert a != b


def test_aggregate_root_is_entity() -> None:
    assert issubclass(AggregateRoot, Entity)


def test_domain_error_to_http() -> None:
    cases = [
        (NotFoundError("Nie znaleziono głosowania"), 404),
        (ConflictError("Użytkownik już oddał głos"), 400),
        (PermissionDeniedError("Brak uprawnień"), 403),
        (UnauthorizedError("Wymagane uwierzytelnienie"), 401),
        (ValidationError("Nieprawidłowe dane"), 422),
    ]
    for err, status in cases:
        assert isinstance(err, DomainError)
        assert err.status_code == status
        assert err.message == str(err)
