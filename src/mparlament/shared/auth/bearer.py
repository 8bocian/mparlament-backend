"""Tolerant Bearer-token extraction (CONVENTIONS C1).

The FE sends ``Authorization: Bearer <X>`` where ``<X>`` is *either* a raw JWT *or* the JSON
string ``{"token":"<jwt>","expiresAt":<ms>}`` (it forwards the whole localStorage blob). This
parser returns the JWT string in both cases, and ``None`` for anything it cannot make sense of
(missing header, wrong scheme, malformed JSON). It never raises — absence of identity is
decided downstream (C2), not here.
"""

from __future__ import annotations

import json

_PREFIX = "Bearer "


def extract_jwt(authorization_header: str | None) -> str | None:
    """Return the JWT embedded in an ``Authorization`` header, or ``None``."""
    if not authorization_header or not authorization_header.startswith(_PREFIX):
        return None

    value = authorization_header[len(_PREFIX) :].strip()
    if not value:
        return None

    if value.startswith("{"):
        try:
            token = json.loads(value).get("token")
        except (ValueError, AttributeError):
            return None
        return token or None

    return value
