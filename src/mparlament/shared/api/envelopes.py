"""Minimal response-envelope helpers (CONVENTIONS C10).

Most wrapping is explicit per route (the FE reads exact keys), so this stays tiny — just the
two shapes that recur across slices. Anything more specific belongs in the slice's router.
"""

from __future__ import annotations

from typing import Any


def wrapped(key: str, value: Any) -> dict[str, Any]:
    """``{key: value}`` — e.g. ``wrapped("user", user)`` -> ``{"user": ...}``."""
    return {key: value}


def success(**extra: Any) -> dict[str, Any]:
    """``{"success": true, **extra}`` — the common mutation acknowledgement shape."""
    return {"success": True, **extra}
