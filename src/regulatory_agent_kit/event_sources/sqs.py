"""SQS event source — long-polls AWS SQS for regulatory events."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from regulatory_agent_kit.event_sources.base import EventCallback, parse_event
from regulatory_agent_kit.exceptions import EventSourceError

logger = logging.getLogger(__name__)

try:
    import boto3  # type: ignore[import-untyped]

    _HAS_BOTO3 = True
except ImportError:  # pragma: no cover
    _HAS_BOTO3 = False


class SQSEventSource:
    """Long-polls an AWS SQS queue and deserializes messages to RegulatoryEvents.

    Successfully processed messages are deleted from the queue.
    Requires the ``boto3`` package.
    """

    def __init__(
        self,
        queue_url: str,
        callback: EventCallback,
        *,
        region_name: str = "us-east-1",
        wait_time_seconds: int = 20,
        max_messages: int = 10,
    ) -> None:
        self._queue_url = queue_url
        self._callback = callback
        self._region_name = region_name
        self._wait_time_seconds = wait_time_seconds
        self._max_messages = max_messages
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._client: Any = None

    async def start(self) -> None:
        """Create the SQS client and begin long-polling."""
        if not _HAS_BOTO3:
            msg = "boto3 is not installed. Install it with: pip install boto3"
            raise EventSourceError(msg)
        self._client = boto3.client("sqs", region_name=self._region_name)
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        """Stop polling."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        self._client = None

    async def _poll_loop(self) -> None:
        """Continuously long-poll SQS for messages."""
        loop = asyncio.get_running_loop()
        while self._running:
            try:
                response = await loop.run_in_executor(None, self._receive_messages)
                messages = response.get("Messages", [])
                for msg in messages:
                    await self._handle_message(msg)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Error in SQS poll loop")

    def _receive_messages(self) -> dict[str, Any]:
        """Synchronous SQS receive call (run in executor)."""
        return self._client.receive_message(  # type: ignore[no-any-return]
            QueueUrl=self._queue_url,
            MaxNumberOfMessages=self._max_messages,
            WaitTimeSeconds=self._wait_time_seconds,
        )

    async def _handle_message(self, msg: dict[str, Any]) -> None:
        """Deserialize, dispatch, and delete a single SQS message."""
        body = msg.get("Body", "")
        receipt_handle = msg.get("ReceiptHandle", "")

        event = parse_event(body, source_label="SQS message")
        if event is None:
            return

        await self._callback(event)
        await self._delete_message(receipt_handle)

    async def _delete_message(self, receipt_handle: str) -> None:
        """Delete a successfully processed message from the queue."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: self._client.delete_message(
                QueueUrl=self._queue_url,
                ReceiptHandle=receipt_handle,
            ),
        )
