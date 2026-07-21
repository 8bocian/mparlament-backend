"""Framework-free domain base building blocks.

``Entity`` gives every domain object identity semantics: two entities are equal when they
are the same concrete type and share a persisted ``id``. Entities without an ``id`` (not yet
persisted) fall back to Python object identity. ``AggregateRoot`` is a marker for the roots
that own a consistency boundary (Voting, Resolution, Session, Club, Parliamentarian, User).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(eq=False)
class Entity:
    """Base for domain entities; equality by concrete type + ``id``."""

    id: int | None = None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        if type(self) is not type(other):
            return False
        if self.id is None or other.id is None:
            return self is other
        return self.id == other.id

    def __hash__(self) -> int:
        return hash((type(self).__name__, self.id)) if self.id is not None else id(self)


@dataclass(eq=False)
class AggregateRoot(Entity):
    """Marker base for aggregate roots (consistency boundaries)."""
