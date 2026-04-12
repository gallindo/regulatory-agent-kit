"""Repository Protocol interfaces for Dependency Inversion.

Defines ``Protocol`` classes that abstract the persistence layer, allowing
the orchestration code to depend on interfaces rather than concrete
SQLite or PostgreSQL implementations.
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from typing import Any, Protocol, runtime_checkable
from uuid import UUID  # noqa: TC003


@runtime_checkable
class PipelineRunStore(Protocol):
    """Store for pipeline run lifecycle records."""

    async def create(
        self,
        regulation_id: str,
        total_repos: int,
        config_snapshot: dict[str, Any],
    ) -> UUID: ...

    async def get(self, run_id: UUID) -> dict[str, Any] | None: ...

    async def update_status(self, run_id: UUID, status: str) -> None: ...


@runtime_checkable
class RepositoryProgressStore(Protocol):
    """Store for per-repository processing progress."""

    async def create(self, run_id: UUID, repo_url: str) -> UUID: ...

    async def update_status(self, entry_id: UUID, status: str) -> None: ...

    async def get_by_run(self, run_id: UUID) -> list[dict[str, Any]]: ...


@runtime_checkable
class AuditStore(Protocol):
    """Append-only store for audit trail entries."""

    async def insert(
        self,
        run_id: UUID,
        event_type: str,
        timestamp: datetime,
        payload: dict[str, Any],
        signature: str,
    ) -> UUID: ...

    async def get_by_run(self, run_id: UUID) -> list[dict[str, Any]]: ...


@runtime_checkable
class PluginRegistryStore(Protocol):
    """Store for published regulation plugins and their versions."""

    async def publish(
        self,
        plugin_id: str,
        name: str,
        version: str,
        jurisdiction: str,
        authority: str,
        description: str,
        author: str,
        tags: list[str],
        certification_tier: str,
        yaml_hash: str,
        yaml_content: dict[str, Any],
        changelog: str = "",
    ) -> dict[str, Any]: ...

    async def get(self, plugin_id: str) -> dict[str, Any] | None: ...

    async def search(
        self,
        query: str = "",
        jurisdiction: str | None = None,
        tags: list[str] | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]: ...

    async def list_versions(self, plugin_id: str) -> list[dict[str, Any]]: ...

    async def get_version(
        self, plugin_id: str, version: str
    ) -> dict[str, Any] | None: ...


@runtime_checkable
class CheckpointStore(Protocol):
    """Store for human-in-the-loop checkpoint decisions."""

    async def create(
        self,
        run_id: UUID,
        checkpoint_type: str,
        actor: str,
        decision: str,
        signature: str,
        rationale: str | None = None,
    ) -> UUID: ...

    async def get_by_run(self, run_id: UUID) -> list[dict[str, Any]]: ...
