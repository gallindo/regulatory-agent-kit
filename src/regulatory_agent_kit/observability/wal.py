"""Write-ahead log for audit entries — crash-resilient buffer before DB insert."""

from __future__ import annotations

import json
import logging
from pathlib import Path  # noqa: TC003
from typing import Any

from regulatory_agent_kit.database.repositories.audit_entries import (
    AuditRepository,  # noqa: TC001
)

logger = logging.getLogger(__name__)


class WriteAheadLog:
    """Append-only JSON-lines WAL for audit entries.

    Entries are written to a local file first, then replayed into the
    database.  Corrupted lines (truncated writes, invalid JSON) are
    skipped with a warning so that healthy entries are never lost.
    """

    def __init__(self, wal_path: Path) -> None:
        self._path = wal_path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def write(self, entry: dict[str, Any]) -> None:
        """Append a single audit entry as a JSON line.

        Args:
            entry: Serializable dict representing an audit entry.
        """
        line = json.dumps(entry, default=str)
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    # ------------------------------------------------------------------
    # Replay
    # ------------------------------------------------------------------

    async def replay(self, repo: AuditRepository) -> int:
        """Replay all WAL entries into the database, then truncate the file.

        Returns:
            The number of entries successfully replayed.
        """
        if not self._path.exists():
            return 0

        entries: list[dict[str, Any]] = []
        with self._path.open("r", encoding="utf-8") as fh:
            for lineno, raw_line in enumerate(fh, start=1):
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    entry = json.loads(raw_line)
                except json.JSONDecodeError:
                    logger.warning(
                        "WAL corruption at line %d — skipping invalid JSON.",
                        lineno,
                    )
                    continue
                entries.append(entry)

        if entries:
            await repo.bulk_insert(entries)

        # Truncate after successful replay.
        self._path.write_text("", encoding="utf-8")
        logger.info("WAL replayed %d entries and cleared.", len(entries))
        return len(entries)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def path(self) -> Path:
        """Return the WAL file path."""
        return self._path
