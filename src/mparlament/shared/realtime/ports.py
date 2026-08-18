"""``EventPublisher`` port + process-global registry (doc 10 / spec §5).

Realtime is deliberately decoupled from the write use cases: they depend only on the
:class:`EventPublisher` Protocol and emit a single call at their hook points (doc 10). In v1 the
registered publisher is a :class:`NullEventPublisher` no-op, so emitting is free and the REST +
3-second FE polling contract is unaffected. When Socket.IO is wired (``main.create_asgi_app``) a
concrete adapter is registered via :func:`set_event_publisher` and the same emit calls light up.

The router-level use-case singletons hold :data:`deferred_event_publisher`, which resolves the
current global at emit time (late binding) — so wiring the real publisher after import still
reaches the already-constructed use cases, mirroring the ``set_user_reader`` idiom (doc 01).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class EventPublisher(Protocol):
    """Broadcasts a realtime event to connected clients (S→C)."""

    async def emit(self, event: str, data: object) -> None: ...


class NullEventPublisher:
    """No-op publisher — the v1 default (realtime deferred; REST + polling covers correctness)."""

    async def emit(self, event: str, data: object) -> None:
        return None


_publisher: EventPublisher = NullEventPublisher()


def set_event_publisher(publisher: EventPublisher) -> None:
    """Register the process-wide publisher (called by the Socket.IO wiring)."""
    global _publisher
    _publisher = publisher


def get_event_publisher() -> EventPublisher:
    """Return the currently registered publisher."""
    return _publisher


def reset_event_publisher() -> None:
    """Restore the no-op default (used by tests to isolate global state)."""
    global _publisher
    _publisher = NullEventPublisher()


class DeferredEventPublisher:
    """Late-binding proxy: forwards to whatever :func:`get_event_publisher` returns at emit time.

    Held by the use-case singletons so registering the real publisher *after* the routers are
    imported still takes effect, without re-wiring the use cases.
    """

    async def emit(self, event: str, data: object) -> None:
        await get_event_publisher().emit(event, data)


deferred_event_publisher = DeferredEventPublisher()
