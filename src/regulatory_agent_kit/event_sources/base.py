"""EventSource protocol — the contract all event sources must satisfy."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class EventSource(Protocol):
    """Protocol for pluggable event sources.

    All event sources must implement async ``start()`` and ``stop()`` methods.
    ``start()`` begins producing :class:`RegulatoryEvent` instances (typically
    by invoking a callback), and ``stop()`` performs graceful shutdown.
    """

    async def start(self) -> None:
        """Begin listening for / polling events."""
        ...

    async def stop(self) -> None:
        """Gracefully shut down the event source."""
        ...
