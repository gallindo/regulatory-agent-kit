"""EventSource protocol and shared utilities for event sources."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Coroutine
from typing import Any, Protocol, runtime_checkable

from pydantic import ValidationError

from regulatory_agent_kit.models.events import RegulatoryEvent

logger = logging.getLogger(__name__)

# Shared callback type used by all event sources.
EventCallback = Callable[[RegulatoryEvent], Coroutine[Any, Any, None]]


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


def parse_event(raw: str, *, source_label: str = "message") -> RegulatoryEvent | None:
    """Parse a raw JSON string into a RegulatoryEvent.

    Returns the event on success, or ``None`` on failure (with a warning logged).
    This eliminates the duplicated try/except JSON + Pydantic pattern
    across file, Kafka, and SQS event sources.
    """
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.warning("Failed to decode %s as JSON", source_label)
        return None

    try:
        return RegulatoryEvent.model_validate(data)
    except ValidationError:
        logger.warning("Invalid event schema in %s", source_label)
        return None
