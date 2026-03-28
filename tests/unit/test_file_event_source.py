"""Unit tests for FileEventSource."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path  # noqa: TC003
from unittest.mock import AsyncMock

import pytest

from regulatory_agent_kit.event_sources.file import FileEventSource
from regulatory_agent_kit.exceptions import EventSourceError
from regulatory_agent_kit.models.events import RegulatoryEvent


def _write_event_json(directory: Path, filename: str, data: dict[str, object]) -> Path:
    """Write a JSON file into *directory* and return its path."""
    path = directory / filename
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _valid_event_data() -> dict[str, str]:
    return {
        "regulation_id": "dora-ict-risk-2025",
        "change_type": "new_requirement",
        "source": "file_watcher",
    }


class TestFileEventSource:
    """Tests for the file-watcher event source."""

    async def test_produces_event_from_valid_json(self, tmp_path: Path) -> None:
        callback = AsyncMock()
        source = FileEventSource(tmp_path, callback, poll_interval=0.1)
        _write_event_json(tmp_path, "evt1.json", _valid_event_data())

        await source.start()
        await asyncio.sleep(0.3)
        await source.stop()

        callback.assert_called_once()
        event = callback.call_args[0][0]
        assert isinstance(event, RegulatoryEvent)
        assert event.regulation_id == "dora-ict-risk-2025"

    async def test_removes_file_after_processing(self, tmp_path: Path) -> None:
        callback = AsyncMock()
        source = FileEventSource(tmp_path, callback, poll_interval=0.1)
        file_path = _write_event_json(tmp_path, "evt.json", _valid_event_data())

        await source.start()
        await asyncio.sleep(0.3)
        await source.stop()

        assert not file_path.exists()

    async def test_ignores_non_json_files(self, tmp_path: Path) -> None:
        callback = AsyncMock()
        source = FileEventSource(tmp_path, callback, poll_interval=0.1)
        (tmp_path / "readme.txt").write_text("hello")

        await source.start()
        await asyncio.sleep(0.3)
        await source.stop()

        callback.assert_not_called()

    async def test_ignores_malformed_json(self, tmp_path: Path) -> None:
        callback = AsyncMock()
        source = FileEventSource(tmp_path, callback, poll_interval=0.1)
        (tmp_path / "bad.json").write_text("{not valid json", encoding="utf-8")

        await source.start()
        await asyncio.sleep(0.3)
        await source.stop()

        callback.assert_not_called()

    async def test_ignores_invalid_event_schema(self, tmp_path: Path) -> None:
        callback = AsyncMock()
        source = FileEventSource(tmp_path, callback, poll_interval=0.1)
        _write_event_json(tmp_path, "bad_schema.json", {"foo": "bar"})

        await source.start()
        await asyncio.sleep(0.3)
        await source.stop()

        callback.assert_not_called()

    async def test_raises_on_missing_directory(self, tmp_path: Path) -> None:
        callback = AsyncMock()
        missing = tmp_path / "nonexistent"
        source = FileEventSource(missing, callback)

        with pytest.raises(EventSourceError, match="does not exist"):
            await source.start()

    async def test_multiple_files_processed(self, tmp_path: Path) -> None:
        callback = AsyncMock()
        source = FileEventSource(tmp_path, callback, poll_interval=0.1)

        for i in range(3):
            _write_event_json(tmp_path, f"evt{i}.json", _valid_event_data())

        await source.start()
        await asyncio.sleep(0.3)
        await source.stop()

        assert callback.call_count == 3
