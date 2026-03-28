"""Unit tests for KafkaEventSource."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

from regulatory_agent_kit.event_sources.kafka import KafkaEventSource
from regulatory_agent_kit.models.events import RegulatoryEvent


def _valid_event_data() -> dict[str, str]:
    return {
        "regulation_id": "dora-ict-risk-2025",
        "change_type": "new_requirement",
        "source": "kafka",
    }


class TestKafkaEventSource:
    """Tests for the Kafka event source."""

    async def test_handles_valid_message(self) -> None:
        callback = AsyncMock()
        source = KafkaEventSource("test-topic", callback)

        msg = MagicMock()
        msg.value.return_value = json.dumps(_valid_event_data()).encode()

        await source._handle_message(msg)

        callback.assert_called_once()
        event = callback.call_args[0][0]
        assert isinstance(event, RegulatoryEvent)
        assert event.regulation_id == "dora-ict-risk-2025"

    async def test_handles_invalid_json(self) -> None:
        callback = AsyncMock()
        source = KafkaEventSource("test-topic", callback)

        msg = MagicMock()
        msg.value.return_value = b"not json"

        await source._handle_message(msg)
        callback.assert_not_called()

    async def test_handles_invalid_event_schema(self) -> None:
        callback = AsyncMock()
        source = KafkaEventSource("test-topic", callback)

        msg = MagicMock()
        msg.value.return_value = json.dumps({"bad": "data"}).encode()

        await source._handle_message(msg)
        callback.assert_not_called()

    async def test_handles_none_value(self) -> None:
        callback = AsyncMock()
        source = KafkaEventSource("test-topic", callback)

        msg = MagicMock()
        msg.value.return_value = None

        await source._handle_message(msg)
        callback.assert_not_called()
