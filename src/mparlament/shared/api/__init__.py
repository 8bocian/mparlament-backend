"""Shared HTTP glue: exception handlers + envelope helpers."""

from __future__ import annotations

from mparlament.shared.api.envelopes import success, wrapped
from mparlament.shared.api.exceptions import register_exception_handlers

__all__ = ["register_exception_handlers", "success", "wrapped"]
