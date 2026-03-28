"""Tests for audit storage backends and archiver (Phase 8)."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003
from unittest.mock import MagicMock

import pytest

from regulatory_agent_kit.observability.storage import (
    AuditArchiver,
    LocalStorageBackend,
    StorageBackend,
)

# ------------------------------------------------------------------
# LocalStorageBackend
# ------------------------------------------------------------------


class TestLocalStorageBackend:
    def test_upload_creates_file(self, tmp_path: Path) -> None:
        backend = LocalStorageBackend(root=tmp_path)
        backend.upload(b"hello world", "reports/2026/01/report.json")
        dest = tmp_path / "reports" / "2026" / "01" / "report.json"
        assert dest.exists()
        assert dest.read_bytes() == b"hello world"

    def test_download_returns_bytes(self, tmp_path: Path) -> None:
        backend = LocalStorageBackend(root=tmp_path)
        backend.upload(b"test data", "file.bin")
        assert backend.download("file.bin") == b"test data"

    def test_download_missing_file_raises(self, tmp_path: Path) -> None:
        backend = LocalStorageBackend(root=tmp_path)
        with pytest.raises(FileNotFoundError):
            backend.download("nonexistent.bin")

    def test_implements_protocol(self, tmp_path: Path) -> None:
        backend = LocalStorageBackend(root=tmp_path)
        assert isinstance(backend, StorageBackend)


# ------------------------------------------------------------------
# AuditArchiver
# ------------------------------------------------------------------


class TestAuditArchiver:
    def test_export_partition_creates_file(self, tmp_path: Path) -> None:
        archiver = AuditArchiver(lite_mode=True, local_root=tmp_path / "archive")
        export_file = archiver.export_partition(2026, 3, tmp_path / "export")
        assert export_file.exists()
        content = export_file.read_text(encoding="utf-8")
        assert "2026-03" in content

    def test_upload_report_delegates_to_backend(self, tmp_path: Path) -> None:
        mock_backend = MagicMock(spec=StorageBackend)
        archiver = AuditArchiver(backend=mock_backend)

        report = tmp_path / "report.json"
        report.write_bytes(b'{"status": "ok"}')

        archiver.upload_report(report, "dest/report.json")
        mock_backend.upload.assert_called_once_with(b'{"status": "ok"}', "dest/report.json")

    def test_export_partition_subdirectory_structure(self, tmp_path: Path) -> None:
        archiver = AuditArchiver(lite_mode=True, local_root=tmp_path / "archive")
        export_file = archiver.export_partition(2025, 12, tmp_path / "out")
        assert export_file.parent.name == "12"
        assert export_file.parent.parent.name == "2025"


# ------------------------------------------------------------------
# Lite Mode always uses local backend
# ------------------------------------------------------------------


class TestLiteMode:
    def test_lite_mode_uses_local_backend(self, tmp_path: Path) -> None:
        archiver = AuditArchiver(lite_mode=True, local_root=tmp_path)
        assert isinstance(archiver.backend, LocalStorageBackend)

    def test_no_backend_defaults_to_local(self) -> None:
        archiver = AuditArchiver(backend=None)
        assert isinstance(archiver.backend, LocalStorageBackend)

    def test_lite_mode_overrides_provided_backend(self, tmp_path: Path) -> None:
        mock_backend = MagicMock(spec=StorageBackend)
        archiver = AuditArchiver(backend=mock_backend, lite_mode=True, local_root=tmp_path)
        assert isinstance(archiver.backend, LocalStorageBackend)
