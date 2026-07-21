"""Central import point for every slice's ORM models.

Importing this module guarantees all tables are registered on ``Base.metadata`` before
Alembic autogenerate or ``Base.metadata.create_all`` runs. Each slice appends its model
imports here as it is built (slice 00 has no models yet).
"""

from __future__ import annotations

from mparlament.shared.db import Base

# Slice models are imported below as slices are implemented, e.g.:
#   from mparlament.slices.auth_identity.infrastructure.models import UserModel  # noqa: F401

__all__ = ["Base"]
