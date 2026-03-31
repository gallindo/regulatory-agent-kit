"""Kafka event source — wraps confluent_kafka.Consumer for regulatory events."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

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


class CredentialReloader:
    """Watches a JSON credentials file for changes and invokes a callback.

    The credentials file must contain a JSON object with ``username`` and
    ``password`` keys.  When the file's modification time changes, the
    new credentials are read and ``on_rotate`` is called.
    """

    def __init__(
        self,
        credential_path: str,
        on_rotate: Callable[[str, str], Any],
        poll_interval: float = 5.0,
    ) -> None:
        self._credential_path = credential_path
        self._on_rotate = on_rotate
        self._poll_interval = poll_interval
        self._last_mtime: float | None = None
        self._lock = threading.Lock()
        self._task: asyncio.Task[None] | None = None
        self._running = False

    def _read_credentials(self) -> tuple[str, str]:
        """Read and parse the credentials file.

        Returns:
            A ``(username, password)`` tuple.

        Raises:
            EventSourceError: If the file cannot be read or parsed.
        """
        try:
            with open(self._credential_path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            msg = f"Failed to read credentials file: {self._credential_path}"
            raise EventSourceError(msg) from exc

        username = data.get("username")
        password = data.get("password")
        if not username or not password:
            msg = (
                f"Credentials file {self._credential_path} must contain "
                "'username' and 'password' keys"
            )
            raise EventSourceError(msg)
        return str(username), str(password)

    def _current_mtime(self) -> float | None:
        """Return the modification time of the credentials file, or None."""
        try:
            return os.path.getmtime(self._credential_path)
        except OSError:
            return None

    def check_for_update(self) -> bool:
        """Check whether the credentials file has changed since last check.

        If a change is detected the ``on_rotate`` callback is invoked with
        the new ``(username, password)`` and ``True`` is returned.  Returns
        ``False`` when the file is unchanged or cannot be read.
        """
        mtime = self._current_mtime()
        if mtime is None:
            return False

        with self._lock:
            if self._last_mtime is not None and mtime == self._last_mtime:
                return False
            self._last_mtime = mtime

        try:
            username, password = self._read_credentials()
        except EventSourceError:
            logger.warning(
                "Credential file changed but could not be read",
                exc_info=True,
            )
            return False

        self._on_rotate(username, password)
        logger.info("Kafka credentials rotated from %s", self._credential_path)
        return True

    async def start(self) -> None:
        """Begin polling the credentials file for changes."""
        # Record the initial mtime so the first real change is detected.
        self._last_mtime = self._current_mtime()
        self._running = True
        self._task = asyncio.create_task(self._watch_loop())

    async def stop(self) -> None:
        """Stop the credential watch loop."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _watch_loop(self) -> None:
        """Periodically check the credentials file for modifications."""
        while self._running:
            try:
                self.check_for_update()
                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.warning("Error in credential watch loop", exc_info=True)


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
        self._credential_lock = threading.Lock()
        self._credential_reloader: CredentialReloader | None = None

    # --- Credential rotation --------------------------------------------------

    def rotate_credentials(self, username: str, password: str) -> None:
        """Update SASL credentials and reconnect the Kafka consumer.

        This method is thread-safe and can be called from any thread,
        including the ``CredentialReloader`` callback.

        Args:
            username: New SASL username.
            password: New SASL password.
        """
        with self._credential_lock:
            new_config = dict(self._config.consumer_config)
            new_config["sasl.username"] = username
            new_config["sasl.password"] = password
            self._config = KafkaConfig(
                topic=self._config.topic,
                consumer_config=new_config,
                poll_timeout=self._config.poll_timeout,
            )

            if self._consumer is not None:
                try:
                    self._consumer.close()
                except Exception:
                    logger.warning(
                        "Error closing old Kafka consumer during credential rotation",
                        exc_info=True,
                    )

                if _HAS_KAFKA:
                    self._consumer = Consumer(self._config.consumer_config)
                    self._consumer.subscribe([self._config.topic])

        logger.info("Kafka consumer reconnected with rotated credentials")

    async def start_credential_watch(
        self,
        credential_path: str,
        poll_interval: float = 5.0,
    ) -> None:
        """Start watching a credentials file for changes.

        When the file's modification time changes, the new credentials are
        read and applied via :meth:`rotate_credentials`.

        Args:
            credential_path: Path to a JSON file with ``username``/``password``.
            poll_interval: Seconds between file-stat checks.
        """
        if self._credential_reloader is not None:
            await self.stop_credential_watch()

        self._credential_reloader = CredentialReloader(
            credential_path=credential_path,
            on_rotate=self.rotate_credentials,
            poll_interval=poll_interval,
        )
        await self._credential_reloader.start()

    async def stop_credential_watch(self) -> None:
        """Stop the credential file watcher, if running."""
        if self._credential_reloader is not None:
            await self._credential_reloader.stop()
            self._credential_reloader = None

    # --- Core consumer lifecycle ----------------------------------------------

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
        """Stop polling, close the Kafka consumer, and stop credential watch."""
        self._running = False
        await self.stop_credential_watch()
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
                with self._credential_lock:
                    consumer = self._consumer
                if consumer is None:
                    await asyncio.sleep(0.1)
                    continue
                msg = await loop.run_in_executor(None, consumer.poll, self._config.poll_timeout)
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
                logger.warning("Error in Kafka poll loop", exc_info=True)

    async def _handle_message(self, msg: Any) -> None:
        """Deserialize and dispatch a single Kafka message."""
        raw = msg.value()
        if raw is None:
            return

        event = parse_event(raw, source_label="Kafka message")
        if event is not None:
            await self._callback(event)
