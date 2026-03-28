"""Tests for the Write-Ahead Log (Phase 8)."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from regulatory_agent_kit.observability.wal import WriteAheadLog

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def wal_path(tmp_path: Path) -> Path:
    return tmp_path / "audit.wal"


@pytest.fixture
def wal(wal_path: Path) -> WriteAheadLog:
    return WriteAheadLog(wal_path)


@pytest.fixture
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.bulk_insert = AsyncMock(return_value=[uuid4()])
    return repo


def _make_entry(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "run_id": str(uuid4()),
        "event_type": "llm_call",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "payload": {"model": "claude"},
        "signature": "c2lnbmVk",
    }
    base.update(overrides)
    return base


# ------------------------------------------------------------------
# Write / replay cycle
# ------------------------------------------------------------------


class TestWriteReplayCycle:
    async def test_write_then_replay(self, wal: WriteAheadLog, mock_repo: AsyncMock) -> None:
        entry = _make_entry()
        wal.write(entry)
        replayed = await wal.replay(mock_repo)
        assert replayed == 1
        mock_repo.bulk_insert.assert_awaited_once()

    async def test_multiple_entries(self, wal: WriteAheadLog, mock_repo: AsyncMock) -> None:
        for _ in range(5):
            wal.write(_make_entry())
        replayed = await wal.replay(mock_repo)
        assert replayed == 5

    async def test_wal_cleared_after_replay(
        self, wal: WriteAheadLog, mock_repo: AsyncMock
    ) -> None:
        wal.write(_make_entry())
        await wal.replay(mock_repo)
        # File should be empty after replay.
        assert wal.path.read_text(encoding="utf-8") == ""

    async def test_replay_empty_wal(self, wal: WriteAheadLog, mock_repo: AsyncMock) -> None:
        # WAL file does not exist yet.
        replayed = await wal.replay(mock_repo)
        assert replayed == 0
        mock_repo.bulk_insert.assert_not_awaited()


# ------------------------------------------------------------------
# Corruption recovery
# ------------------------------------------------------------------


class TestCorruptionRecovery:
    async def test_skip_invalid_json_lines(
        self, wal: WriteAheadLog, wal_path: Path, mock_repo: AsyncMock
    ) -> None:
        # Write one valid entry, one corrupt line, one valid entry.
        valid = _make_entry()
        wal.write(valid)
        with wal_path.open("a", encoding="utf-8") as fh:
            fh.write("NOT VALID JSON\n")
        wal.write(_make_entry())

        replayed = await wal.replay(mock_repo)
        assert replayed == 2
        # bulk_insert should have received exactly 2 entries.
        args = mock_repo.bulk_insert.call_args[0][0]
        assert len(args) == 2

    async def test_truncated_file(
        self, wal: WriteAheadLog, wal_path: Path, mock_repo: AsyncMock
    ) -> None:
        wal.write(_make_entry())
        # Truncate mid-line to simulate a crash.
        content = wal_path.read_text(encoding="utf-8")
        wal_path.write_text(content[:10], encoding="utf-8")

        replayed = await wal.replay(mock_repo)
        # The truncated line is invalid JSON, so 0 entries replayed.
        assert replayed == 0

    async def test_blank_lines_ignored(
        self, wal: WriteAheadLog, wal_path: Path, mock_repo: AsyncMock
    ) -> None:
        wal.write(_make_entry())
        with wal_path.open("a", encoding="utf-8") as fh:
            fh.write("\n\n\n")
        wal.write(_make_entry())

        replayed = await wal.replay(mock_repo)
        assert replayed == 2
