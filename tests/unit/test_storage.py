"""Tests for audit storage backends and archiver."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003
from unittest.mock import MagicMock, patch

import pytest

from regulatory_agent_kit.observability.storage import (
    AuditArchiver,
    AzureBlobStorageBackend,
    GCSStorageBackend,
    LocalStorageBackend,
    S3StorageBackend,
    StorageBackend,
    create_storage_backend,
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
# S3StorageBackend
# ------------------------------------------------------------------


class TestS3StorageBackend:
    def test_upload_calls_put_object(self) -> None:
        mock_client = MagicMock()
        with patch("boto3.client", return_value=mock_client):
            backend = S3StorageBackend(bucket="test-bucket", prefix="audit")
        backend.upload(b"data", "2026/03/report.json")
        mock_client.put_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="audit/2026/03/report.json",
            Body=b"data",
        )

    def test_download_calls_get_object(self) -> None:
        mock_body = MagicMock()
        mock_body.read.return_value = b"downloaded"
        mock_client = MagicMock()
        mock_client.get_object.return_value = {"Body": mock_body}
        with patch("boto3.client", return_value=mock_client):
            backend = S3StorageBackend(bucket="test-bucket", prefix="audit")
        result = backend.download("2026/03/report.json")
        assert result == b"downloaded"
        mock_client.get_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="audit/2026/03/report.json",
        )

    def test_key_without_prefix(self) -> None:
        mock_client = MagicMock()
        with patch("boto3.client", return_value=mock_client):
            backend = S3StorageBackend(bucket="b")
        backend.upload(b"x", "path/file.txt")
        mock_client.put_object.assert_called_once_with(
            Bucket="b", Key="path/file.txt", Body=b"x",
        )

    def test_implements_protocol(self) -> None:
        mock_client = MagicMock()
        with patch("boto3.client", return_value=mock_client):
            backend = S3StorageBackend(bucket="b")
        assert isinstance(backend, StorageBackend)


# ------------------------------------------------------------------
# GCSStorageBackend
# ------------------------------------------------------------------


class TestGCSStorageBackend:
    def test_raises_if_gcs_not_installed(self) -> None:
        with (
            patch("regulatory_agent_kit.observability.storage._HAS_GCS", False),
            pytest.raises(ImportError, match="google-cloud-storage"),
        ):
            GCSStorageBackend(bucket="b")

    def test_upload_calls_blob_upload(self) -> None:
        mock_blob = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_bucket.name = "test-bucket"
        mock_gcs_client = MagicMock()
        mock_gcs_client.bucket.return_value = mock_bucket

        with (
            patch(
                "regulatory_agent_kit.observability.storage._HAS_GCS", True
            ),
            patch(
                "regulatory_agent_kit.observability.storage.gcs_storage",
                create=True,
            ) as mock_mod,
        ):
            mock_mod.Client.return_value = mock_gcs_client
            backend = GCSStorageBackend(bucket="test-bucket", prefix="data")

        backend.upload(b"content", "file.json")
        mock_bucket.blob.assert_called_once_with("data/file.json")
        mock_blob.upload_from_string.assert_called_once_with(b"content")

    def test_download_calls_blob_download(self) -> None:
        mock_blob = MagicMock()
        mock_blob.download_as_bytes.return_value = b"fetched"
        mock_bucket = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_gcs_client = MagicMock()
        mock_gcs_client.bucket.return_value = mock_bucket

        with (
            patch(
                "regulatory_agent_kit.observability.storage._HAS_GCS", True
            ),
            patch(
                "regulatory_agent_kit.observability.storage.gcs_storage",
                create=True,
            ) as mock_mod,
        ):
            mock_mod.Client.return_value = mock_gcs_client
            backend = GCSStorageBackend(bucket="test-bucket")

        result = backend.download("file.json")
        assert result == b"fetched"


# ------------------------------------------------------------------
# AzureBlobStorageBackend
# ------------------------------------------------------------------


class TestAzureBlobStorageBackend:
    def test_raises_if_azure_not_installed(self) -> None:
        with (
            patch("regulatory_agent_kit.observability.storage._HAS_AZURE", False),
            pytest.raises(ImportError, match="azure-storage-blob"),
        ):
            AzureBlobStorageBackend(
                connection_string="conn", container="c"
            )

    def test_upload_calls_upload_blob(self) -> None:
        mock_container = MagicMock()
        mock_service = MagicMock()
        mock_service.get_container_client.return_value = mock_container

        with (
            patch(
                "regulatory_agent_kit.observability.storage._HAS_AZURE", True
            ),
            patch(
                "regulatory_agent_kit.observability.storage.BlobServiceClient",
                create=True,
            ) as mock_cls,
        ):
            mock_cls.from_connection_string.return_value = mock_service
            backend = AzureBlobStorageBackend(
                connection_string="conn", container="c", prefix="pfx"
            )

        backend.upload(b"data", "file.json")
        mock_container.upload_blob.assert_called_once_with(
            "pfx/file.json", b"data", overwrite=True
        )

    def test_download_calls_download_blob(self) -> None:
        mock_download = MagicMock()
        mock_download.readall.return_value = b"azure-data"
        mock_blob_client = MagicMock()
        mock_blob_client.download_blob.return_value = mock_download
        mock_container = MagicMock()
        mock_container.get_blob_client.return_value = mock_blob_client
        mock_service = MagicMock()
        mock_service.get_container_client.return_value = mock_container

        with (
            patch(
                "regulatory_agent_kit.observability.storage._HAS_AZURE", True
            ),
            patch(
                "regulatory_agent_kit.observability.storage.BlobServiceClient",
                create=True,
            ) as mock_cls,
        ):
            mock_cls.from_connection_string.return_value = mock_service
            backend = AzureBlobStorageBackend(
                connection_string="conn", container="c"
            )

        result = backend.download("file.json")
        assert result == b"azure-data"


# ------------------------------------------------------------------
# create_storage_backend factory
# ------------------------------------------------------------------


class TestCreateStorageBackend:
    def test_local_default(self) -> None:
        backend = create_storage_backend("local")
        assert isinstance(backend, LocalStorageBackend)

    def test_local_with_root(self, tmp_path: Path) -> None:
        backend = create_storage_backend("local", local_root=tmp_path / "data")
        assert isinstance(backend, LocalStorageBackend)

    def test_s3(self) -> None:
        mock_client = MagicMock()
        with patch("boto3.client", return_value=mock_client):
            backend = create_storage_backend(
                "s3", s3_bucket="bucket", s3_prefix="pre"
            )
        assert isinstance(backend, S3StorageBackend)

    def test_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown storage backend"):
            create_storage_backend("unknown")


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

    def test_export_partition_with_entries(self, tmp_path: Path) -> None:
        archiver = AuditArchiver(lite_mode=True, local_root=tmp_path / "archive")
        entries = [
            {"event_type": "llm_call", "model": "claude", "cost": 0.01},
            {"event_type": "tool_invocation", "tool": "git_clone"},
        ]
        export_file = archiver.export_partition(
            2026, 3, tmp_path / "export", entries=entries
        )
        assert export_file.exists()
        lines = export_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        assert "llm_call" in lines[0]
        assert "git_clone" in lines[1]

    def test_archive_partition_exports_and_uploads(self, tmp_path: Path) -> None:
        archive_root = tmp_path / "backend"
        archiver = AuditArchiver(
            lite_mode=True, local_root=archive_root
        )
        entries = [{"event_type": "state_transition", "phase": "ANALYZING"}]
        dest_key = archiver.archive_partition(
            2026, 3, tmp_path / "export", entries=entries
        )
        assert dest_key == "audit-archives/2026/03/audit_entries.jsonl"
        # Verify the file was uploaded to the local backend
        uploaded = archive_root / dest_key
        assert uploaded.exists()
        assert "ANALYZING" in uploaded.read_text(encoding="utf-8")

    def test_upload_report_delegates_to_backend(self, tmp_path: Path) -> None:
        mock_backend = MagicMock(spec=StorageBackend)
        archiver = AuditArchiver(backend=mock_backend)

        report = tmp_path / "report.json"
        report.write_bytes(b'{"status": "ok"}')

        archiver.upload_report(report, "dest/report.json")
        mock_backend.upload.assert_called_once_with(
            b'{"status": "ok"}', "dest/report.json"
        )

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
        archiver = AuditArchiver(
            backend=mock_backend, lite_mode=True, local_root=tmp_path
        )
        assert isinstance(archiver.backend, LocalStorageBackend)
