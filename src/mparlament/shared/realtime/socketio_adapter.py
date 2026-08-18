"""Concrete :class:`EventPublisher` backed by a Socket.IO ``AsyncServer`` (doc 10 / spec §5).

Thin adapter: :meth:`emit` broadcasts to every connected client. The event name may embed an id
(``voteUpdate:<votingId>``); the FE subscribes to that exact string. Kept dependency-light (only
``python-socketio``) so it lives in the shared kernel while the *wiring* of a concrete server lives
in the composition root (``main``).
"""

from __future__ import annotations

import socketio


class SocketIOEventPublisher:
    """Broadcast realtime events over a Socket.IO server (S→C)."""

    def __init__(self, sio: socketio.AsyncServer) -> None:
        self._sio = sio

    async def emit(self, event: str, data: object) -> None:
        await self._sio.emit(event, data)
