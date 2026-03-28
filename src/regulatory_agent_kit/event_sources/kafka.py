"""Kafka event source — wraps confluent_kafka.Consumer for regulatory events."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from pydantic import ValidationError

from regulatory_agent_kit.exceptions import EventSourceError
from regulatory_agent_kit.models.events import RegulatoryEvent

logger = logging.getLogger(__name__)

EventCallback = Callable[[RegulatoryEvent], Coroutine[Any, Any, None]]

try:
    from confluent_kafka import Consumer, KafkaError

    _HAS_KAFKA = True
except ImportError:  # pragma: no cover
    _HAS_KAFKA = False


class KafkaEventSource:
    """Consumes messages from a Kafka topic and deserializes to RegulatoryEvents.

    Requires the ``confluent-kafka`` package. If not installed, ``start()``
    raises :class:`EventSourceError`.
    """

    def __init__(
        self,
        topic: str,
        callback: EventCallback,
        *,
        consumer_config: dict[str, Any] | None = None,
        poll_timeout: float = 1.0,
    ) -> None:
        self._topic = topic
        self._callback = callback
        self._consumer_config = consumer_config or {
            "bootstrap.servers": "localhost:9092",
            "group.id": "rak-events",
            "auto.offset.reset": "earliest",
        }
        self._poll_timeout = poll_timeout
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._consumer: Any = None

    async def start(self) -> None:
        """Subscribe to the Kafka topic and begin polling."""
        if not _HAS_KAFKA:
            msg = "confluent-kafka is not installed. Install it with: pip install confluent-kafka"
            raise EventSourceError(msg)
        self._consumer = Consumer(self._consumer_config)
        self._consumer.subscribe([self._topic])
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        """Stop polling and close the Kafka consumer."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if self._consumer is not None:
            self._consumer.close()
            self._consumer = None

    async def _poll_loop(self) -> None:
        """Continuously poll Kafka for messages."""
        loop = asyncio.get_running_loop()
        while self._running:
            try:
                msg = await loop.run_in_executor(None, self._consumer.poll, self._poll_timeout)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    logger.error("Kafka error: %s", msg.error())
                    continue
                await self._handle_message(msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Error in Kafka poll loop")

    async def _handle_message(self, msg: Any) -> None:
        """Deserialize and dispatch a single Kafka message."""
        raw = msg.value()
        if raw is None:
            return

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.error("Failed to decode Kafka message as JSON")
            return

        try:
            event = RegulatoryEvent.model_validate(data)
        except ValidationError:
            logger.error("Invalid event schema in Kafka message")
            return

        await self._callback(event)
