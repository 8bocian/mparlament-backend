"""Shared realtime kernel (doc 10 / spec §5) — the ``EventPublisher`` port + Socket.IO adapter."""

from __future__ import annotations

from mparlament.shared.realtime.ports import (
    DeferredEventPublisher,
    EventPublisher,
    NullEventPublisher,
    deferred_event_publisher,
    get_event_publisher,
    reset_event_publisher,
    set_event_publisher,
)
from mparlament.shared.realtime.socketio_adapter import SocketIOEventPublisher

__all__ = [
    "DeferredEventPublisher",
    "EventPublisher",
    "NullEventPublisher",
    "SocketIOEventPublisher",
    "deferred_event_publisher",
    "get_event_publisher",
    "reset_event_publisher",
    "set_event_publisher",
]
