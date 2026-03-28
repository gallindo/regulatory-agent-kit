"""Kafka event source — wraps confluent_kafka.Consumer for regulatory events."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass, field
from typing import Any

from regulatory_agent_kit.event_sources.base import EventCallback, parse_event
from regulatory_agent_kit.exceptions import EventSourceError

logger = logging.getLogger(__name__)

try:
    from confluent_kafka import Consumer, KafkaError

    _HAS_KAFKA = True
except ImportError:  # pragma: no cover
    _HAS_KAFKA = False


@dataclass(frozen=True)
class KafkaConfig:
    """Configuration value object for :class:`KafkaEventSource`."""

    topic: str
    consumer_config: dict[str, Any] = field(
        default_factory=lambda: {
            "bootstrap.servers": "localhost:9092",
            "group.id": "rak-events",
            "auto.offset.reset": "earliest",
        }
    )
    poll_timeout: float = 1.0


class KafkaEventSource:
    """Consumes messages from a Kafka topic and deserializes to RegulatoryEvents.

    Requires the ``confluent-kafka`` package. If not installed, ``start()``
    raises :class:`EventSourceError`.
    """

    def __init__(
        self,
        config: KafkaConfig,
        callback: EventCallback,
    ) -> None:
        self._config = config
        self._callback = callback
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._consumer: Any = None

    async def start(self) -> None:
        """Subscribe to the Kafka topic and begin polling."""
        if not _HAS_KAFKA:
            msg = "confluent-kafka is not installed. Install it with: pip install confluent-kafka"
            raise EventSourceError(msg)
        self._consumer = Consumer(self._config.consumer_config)
        self._consumer.subscribe([self._config.topic])
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
                msg = await loop.run_in_executor(
                    None, self._consumer.poll, self._config.poll_timeout
                )
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

        event = parse_event(raw, source_label="Kafka message")
        if event is not None:
            await self._callback(event)
