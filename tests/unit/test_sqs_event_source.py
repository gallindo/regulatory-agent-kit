"""Unit tests for SQSEventSource."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from regulatory_agent_kit.event_sources.sqs import SQSEventSource
from regulatory_agent_kit.models.events import RegulatoryEvent


def _valid_event_data() -> dict[str, str]:
    return {
        "regulation_id": "dora-ict-risk-2025",
        "change_type": "new_requirement",
        "source": "sqs",
    }


class TestSQSEventSource:
    """Tests for the SQS event source."""

    async def test_handles_valid_message_and_deletes(self) -> None:
        callback = AsyncMock()
        source = SQSEventSource(
            "https://sqs.us-east-1.amazonaws.com/123/test-queue",
            callback,
        )
        source._client = MagicMock()

        msg: dict[str, Any] = {
            "Body": json.dumps(_valid_event_data()),
            "ReceiptHandle": "receipt-123",
        }

        await source._handle_message(msg)

        callback.assert_called_once()
        event = callback.call_args[0][0]
        assert isinstance(event, RegulatoryEvent)
        assert event.regulation_id == "dora-ict-risk-2025"

    async def test_handles_invalid_json(self) -> None:
        callback = AsyncMock()
        source = SQSEventSource(
            "https://sqs.us-east-1.amazonaws.com/123/test-queue",
            callback,
        )
        source._client = MagicMock()

        msg: dict[str, Any] = {
            "Body": "not json",
            "ReceiptHandle": "receipt-456",
        }

        await source._handle_message(msg)
        callback.assert_not_called()

    async def test_handles_invalid_event_schema(self) -> None:
        callback = AsyncMock()
        source = SQSEventSource(
            "https://sqs.us-east-1.amazonaws.com/123/test-queue",
            callback,
        )
        source._client = MagicMock()

        msg: dict[str, Any] = {
            "Body": json.dumps({"bad": "data"}),
            "ReceiptHandle": "receipt-789",
        }

        await source._handle_message(msg)
        callback.assert_not_called()
