"""Audit archival and storage backends for long-term retention."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)


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
    ) -> Path:
        """Export a monthly audit partition to *output_path*.

        Creates the target directory structure and writes a placeholder
        file.  A real implementation would query the database and serialise
        entries; this version writes the partition metadata so the archiving
        workflow can proceed.

        Returns:
            The path to the exported file.
        """
        partition_dir = output_path / f"{year}" / f"{month:02d}"
        partition_dir.mkdir(parents=True, exist_ok=True)
        export_file = partition_dir / "audit_entries.jsonl"
        export_file.write_text(
            f'{{"partition": "{year}-{month:02d}", "status": "exported"}}\n',
            encoding="utf-8",
        )
        logger.info("Exported partition %04d-%02d to %s", year, month, export_file)
        return export_file

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
