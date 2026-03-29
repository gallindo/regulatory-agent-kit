"""Audit archival and storage backends for long-term retention.

Provides pluggable storage backends (local filesystem, S3, GCS, Azure Blob)
and the ``AuditArchiver`` that exports, serialises, and uploads audit
partition data to the configured backend.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Optional cloud SDK imports
# ------------------------------------------------------------------

try:
    import boto3  # type: ignore[import-untyped]

    _HAS_BOTO3 = True
except ImportError:  # pragma: no cover
    _HAS_BOTO3 = False

try:
    from google.cloud import storage as gcs_storage  # type: ignore[import-untyped]

    _HAS_GCS = True
except ImportError:
    _HAS_GCS = False

try:
    from azure.storage.blob import BlobServiceClient  # type: ignore[import-untyped]

    _HAS_AZURE = True
except ImportError:
    _HAS_AZURE = False


# ------------------------------------------------------------------
# Storage backend protocol
# ------------------------------------------------------------------


@runtime_checkable
class StorageBackend(Protocol):
    """Pluggable interface for uploading and downloading audit artefacts."""

    def upload(self, data: bytes, path: str) -> None:
        """Upload *data* to the given *path*."""
        ...  # pragma: no cover

    def download(self, path: str) -> bytes:
        """Download and return bytes from *path*."""
        ...  # pragma: no cover


# ------------------------------------------------------------------
# Local filesystem backend
# ------------------------------------------------------------------


class LocalStorageBackend:
    """Stores artefacts on the local filesystem.

    This is the default backend used in Lite Mode, where no remote
    object store (S3, GCS, etc.) is available.
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def upload(self, data: bytes, path: str) -> None:
        """Write *data* to ``<root>/<path>``."""
        dest = self._root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        logger.debug("LocalStorageBackend: uploaded %d bytes to %s", len(data), dest)

    def download(self, path: str) -> bytes:
        """Read and return bytes from ``<root>/<path>``."""
        src = self._root / path
        return src.read_bytes()


# ------------------------------------------------------------------
# AWS S3 backend
# ------------------------------------------------------------------


class S3StorageBackend:
    """Stores artefacts in an AWS S3 bucket.

    Requires the ``boto3`` package. Authentication uses the standard
    AWS credential chain (env vars, ~/.aws/credentials, IAM role).

    Args:
        bucket: S3 bucket name.
        prefix: Optional key prefix prepended to all paths.
        region_name: AWS region (defaults to ``us-east-1``).
    """

    def __init__(
        self,
        bucket: str,
        prefix: str = "",
        region_name: str = "us-east-1",
    ) -> None:
        if not _HAS_BOTO3:
            msg = "boto3 is required for S3StorageBackend. Install with: pip install boto3"
            raise ImportError(msg)
        self._bucket = bucket
        self._prefix = prefix.rstrip("/")
        self._client: Any = boto3.client("s3", region_name=region_name)

    def _key(self, path: str) -> str:
        """Build the full S3 key from prefix and path."""
        if self._prefix:
            return f"{self._prefix}/{path}"
        return path

    def upload(self, data: bytes, path: str) -> None:
        """Upload *data* to ``s3://<bucket>/<prefix>/<path>``."""
        key = self._key(path)
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data)
        logger.debug(
            "S3StorageBackend: uploaded %d bytes to s3://%s/%s",
            len(data), self._bucket, key,
        )

    def download(self, path: str) -> bytes:
        """Download and return bytes from ``s3://<bucket>/<prefix>/<path>``."""
        key = self._key(path)
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        data: bytes = response["Body"].read()
        return data


# ------------------------------------------------------------------
# Google Cloud Storage backend
# ------------------------------------------------------------------


class GCSStorageBackend:
    """Stores artefacts in a Google Cloud Storage bucket.

    Requires the ``google-cloud-storage`` package. Authentication uses
    Application Default Credentials.

    Args:
        bucket: GCS bucket name.
        prefix: Optional key prefix prepended to all paths.
    """

    def __init__(self, bucket: str, prefix: str = "") -> None:
        if not _HAS_GCS:
            msg = (
                "google-cloud-storage is required for GCSStorageBackend. "
                "Install with: pip install google-cloud-storage"
            )
            raise ImportError(msg)
        client: Any = gcs_storage.Client()
        self._bucket_obj: Any = client.bucket(bucket)
        self._prefix = prefix.rstrip("/")

    def _key(self, path: str) -> str:
        """Build the full GCS blob name from prefix and path."""
        if self._prefix:
            return f"{self._prefix}/{path}"
        return path

    def upload(self, data: bytes, path: str) -> None:
        """Upload *data* to ``gs://<bucket>/<prefix>/<path>``."""
        key = self._key(path)
        blob: Any = self._bucket_obj.blob(key)
        blob.upload_from_string(data)
        logger.debug(
            "GCSStorageBackend: uploaded %d bytes to gs://%s/%s",
            len(data), self._bucket_obj.name, key,
        )

    def download(self, path: str) -> bytes:
        """Download and return bytes from ``gs://<bucket>/<prefix>/<path>``."""
        key = self._key(path)
        blob: Any = self._bucket_obj.blob(key)
        data: bytes = blob.download_as_bytes()
        return data


# ------------------------------------------------------------------
# Azure Blob Storage backend
# ------------------------------------------------------------------


class AzureBlobStorageBackend:
    """Stores artefacts in Azure Blob Storage.

    Requires the ``azure-storage-blob`` package. Authentication uses
    a connection string.

    Args:
        connection_string: Azure Storage connection string.
        container: Blob container name.
        prefix: Optional key prefix prepended to all paths.
    """

    def __init__(
        self,
        connection_string: str,
        container: str,
        prefix: str = "",
    ) -> None:
        if not _HAS_AZURE:
            msg = (
                "azure-storage-blob is required for AzureBlobStorageBackend. "
                "Install with: pip install azure-storage-blob"
            )
            raise ImportError(msg)
        service_client: Any = BlobServiceClient.from_connection_string(connection_string)
        self._container_client: Any = service_client.get_container_client(container)
        self._prefix = prefix.rstrip("/")

    def _key(self, path: str) -> str:
        """Build the full blob name from prefix and path."""
        if self._prefix:
            return f"{self._prefix}/{path}"
        return path

    def upload(self, data: bytes, path: str) -> None:
        """Upload *data* to the Azure container at ``<prefix>/<path>``."""
        key = self._key(path)
        self._container_client.upload_blob(key, data, overwrite=True)
        logger.debug("AzureBlobStorageBackend: uploaded %d bytes to %s", len(data), key)

    def download(self, path: str) -> bytes:
        """Download and return bytes from the Azure container at ``<prefix>/<path>``."""
        key = self._key(path)
        blob_client: Any = self._container_client.get_blob_client(key)
        data: bytes = blob_client.download_blob().readall()
        return data


# ------------------------------------------------------------------
# Backend factory
# ------------------------------------------------------------------


StorageFactory = Callable[..., StorageBackend]
"""Callable that creates a StorageBackend from keyword arguments."""

_STORAGE_REGISTRY: dict[str, StorageFactory] = {}


def register_storage_backend(name: str, factory: StorageFactory) -> None:
    """Register a storage backend factory by name (Strategy Pattern)."""
    _STORAGE_REGISTRY[name] = factory


# Built-in registrations
register_storage_backend(
    "local",
    lambda **kw: LocalStorageBackend(kw.get("local_root") or Path("audit-archive")),
)
register_storage_backend(
    "s3",
    lambda **kw: S3StorageBackend(
        bucket=kw.get("s3_bucket", ""),
        prefix=kw.get("s3_prefix", ""),
        region_name=kw.get("s3_region", "us-east-1"),
    ),
)
register_storage_backend(
    "gcs",
    lambda **kw: GCSStorageBackend(
        bucket=kw.get("gcs_bucket", ""), prefix=kw.get("gcs_prefix", "")
    ),
)
register_storage_backend(
    "azure",
    lambda **kw: AzureBlobStorageBackend(
        connection_string=kw.get("azure_connection_string", ""),
        container=kw.get("azure_container", ""),
        prefix=kw.get("azure_prefix", ""),
    ),
)


def create_storage_backend(
    backend_type: str = "local",
    **kwargs: Any,
) -> StorageBackend:
    """Create a storage backend via the strategy registry.

    Args:
        backend_type: Registered backend name (``local``, ``s3``, ``gcs``, ``azure``).
        **kwargs: Backend-specific configuration passed to the factory.

    Returns:
        A configured ``StorageBackend`` instance.

    Raises:
        ValueError: If *backend_type* is not registered.
        ImportError: If the required SDK is not installed.
    """
    factory = _STORAGE_REGISTRY.get(backend_type)
    if factory is None:
        registered = ", ".join(sorted(_STORAGE_REGISTRY))
        msg = f"Unknown storage backend: {backend_type!r}. Registered: {registered}"
        raise ValueError(msg)
    return factory(**kwargs)


# ------------------------------------------------------------------
# Audit archiver
# ------------------------------------------------------------------


class AuditArchiver:
    """Exports and uploads partitioned audit data.

    In Lite Mode the archiver always falls back to a
    ``LocalStorageBackend`` so that archives are written to disk.
    """

    def __init__(
        self,
        backend: StorageBackend | None = None,
        *,
        lite_mode: bool = False,
        local_root: Path | None = None,
    ) -> None:
        if lite_mode or backend is None:
            resolved_root = local_root or Path("audit-archive")
            self._backend: StorageBackend = LocalStorageBackend(resolved_root)
        else:
            self._backend = backend

    # ------------------------------------------------------------------
    # Export / upload helpers
    # ------------------------------------------------------------------

    def export_partition(
        self,
        year: int,
        month: int,
        output_path: Path,
        entries: list[dict[str, Any]] | None = None,
    ) -> Path:
        """Export a monthly audit partition to *output_path*.

        When *entries* is provided, each entry is serialised as a JSON
        line.  When ``None``, a metadata-only placeholder is written so
        the archiving workflow can still proceed (useful for dry runs).

        Returns:
            The path to the exported JSONL file.
        """
        partition_dir = output_path / f"{year}" / f"{month:02d}"
        partition_dir.mkdir(parents=True, exist_ok=True)
        export_file = partition_dir / "audit_entries.jsonl"

        if entries:
            lines = [json.dumps(e, default=str) for e in entries]
            export_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        else:
            export_file.write_text(
                json.dumps({"partition": f"{year}-{month:02d}", "status": "exported"}) + "\n",
                encoding="utf-8",
            )

        entry_count = len(entries or [])
        logger.info(
            "Exported partition %04d-%02d to %s (%d entries)",
            year, month, export_file, entry_count,
        )
        return export_file

    def archive_partition(
        self,
        year: int,
        month: int,
        output_path: Path,
        entries: list[dict[str, Any]] | None = None,
    ) -> str:
        """Export a partition to disk and upload it to the storage backend.

        Combines ``export_partition`` and ``upload_report`` into a single
        operation following the bucket structure in data-model.md Section 7.1:
        ``audit-archives/{year}/{month}/audit_entries.jsonl``

        Returns:
            The destination key in the storage backend.
        """
        export_file = self.export_partition(year, month, output_path, entries)
        dest_key = f"audit-archives/{year}/{month:02d}/audit_entries.jsonl"
        self.upload_report(export_file, dest_key)
        return dest_key

    def upload_report(self, report_path: Path, dest: str) -> None:
        """Upload a report file to the configured storage backend.

        Args:
            report_path: Local path of the report to upload.
            dest: Destination key / path in the backend.
        """
        data = report_path.read_bytes()
        self._backend.upload(data, dest)
        logger.info("Uploaded report %s → %s", report_path, dest)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def backend(self) -> StorageBackend:
        """Return the active storage backend."""
        return self._backend
