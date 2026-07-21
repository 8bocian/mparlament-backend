"""Central import point for every slice's ORM models.

Importing this module guarantees all tables are registered on ``Base.metadata`` before
Alembic autogenerate or ``Base.metadata.create_all`` runs. Each slice appends its model
imports here as it is built (slice 00 has no models yet).
"""

from __future__ import annotations

from mparlament.shared.db import Base

# Slice models are imported below as slices are implemented.
from mparlament.slices.auth_identity.infrastructure.models import UserModel  # noqa: F401
from mparlament.slices.sessions.infrastructure.models import (  # noqa: F401
    CurrentSessionModel,
    SessionModel,
    SpeakerModel,
)

__all__ = [
    "Base",
    "CurrentSessionModel",
    "SessionModel",
    "SpeakerModel",
    "UserModel",
]
