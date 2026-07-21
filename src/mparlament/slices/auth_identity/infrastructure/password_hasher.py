"""bcrypt adapter for the ``PasswordHasher`` port (spec §2 domain service).

Uses the ``bcrypt`` library directly: passlib 1.7.4 cannot initialise its bcrypt backend against
bcrypt >= 5.0 (its probe hashes a >72-byte secret, which bcrypt 5.0 now rejects). bcrypt only
considers the first 72 bytes, so we truncate deterministically before hashing/verifying to stay
within that limit (bcrypt 5.0 raises instead of silently truncating). ``verify`` returns ``False``
for a malformed/unknown hash rather than raising, so callers stay simple.
"""

from __future__ import annotations

import bcrypt

_MAX_BYTES = 72


def _prepare(raw: str) -> bytes:
    return raw.encode("utf-8")[:_MAX_BYTES]


class BcryptPasswordHasher:
    """Concrete ``PasswordHasher`` backed by the ``bcrypt`` library."""

    def hash(self, raw: str) -> str:
        return bcrypt.hashpw(_prepare(raw), bcrypt.gensalt()).decode("ascii")

    def verify(self, raw: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(_prepare(raw), hashed.encode("ascii"))
        except (ValueError, TypeError):
            return False
