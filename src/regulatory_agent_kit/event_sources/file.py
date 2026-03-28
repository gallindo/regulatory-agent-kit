"""File-based event source — watches a directory for JSON regulatory events."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Callable, Coroutine
from pathlib import Path  # noqa: TC003
from typing import Any

from pydantic import ValidationError

from regulatory_agent_kit.exceptions import EventSourceError
from regulatory_agent_kit.models.events import RegulatoryEvent

logger = logging.getLogger(__name__)

EventCallback = Callable[[RegulatoryEvent], Coroutine[Any, Any, None]]


class FileEventSource:
    """Watches a directory for JSON files and parses them into RegulatoryEvents.

    Non-JSON files and malformed JSON are logged as warnings and skipped.
    Successfully parsed files are removed after the callback completes.
    """

    def __init__(
        self,
        watch_dir: Path,
        callback: EventCallback,
        *,
        poll_interval: float = 1.0,
    ) -> None:
        self._watch_dir = watch_dir
        self._callback = callback
        self._poll_interval = poll_interval
        self._running = False
        self._task: asyncio.Task[None] | None = None

    @property
    def watch_dir(self) -> Path:
        """Return the watched directory."""
        return self._watch_dir

    async def start(self) -> None:
        """Start polling the watch directory for JSON event files."""
        if not self._watch_dir.is_dir():
            msg = f"Watch directory does not exist: {self._watch_dir}"
            raise EventSourceError(msg)
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        """Stop the polling loop and wait for it to finish."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _poll_loop(self) -> None:
        """Continuously scan for new JSON files."""
        while self._running:
            try:
                await self._scan_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Error during file scan")
            await asyncio.sleep(self._poll_interval)

    async def _scan_once(self) -> None:
        """Scan the directory once and process any JSON files found."""
        for path in sorted(self._watch_dir.iterdir()):
            if not path.is_file():
                continue
            if path.suffix.lower() != ".json":
                logger.warning("Ignoring non-JSON file: %s", path.name)
                continue
            await self._process_file(path)

    async def _process_file(self, path: Path) -> None:
        """Read, validate, and dispatch a single JSON event file."""
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            logger.warning("Could not read file: %s", path.name)
            return

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Malformed JSON in file: %s", path.name)
            return

        try:
            event = RegulatoryEvent.model_validate(data)
        except ValidationError:
            logger.warning("Invalid event schema in file: %s", path.name)
            return

        await self._callback(event)
        path.unlink(missing_ok=True)
