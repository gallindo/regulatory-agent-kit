"""Repository for rak.repository_progress table."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from regulatory_agent_kit.database.repositories.base import BaseRepository


class RepositoryProgressRepository(BaseRepository):
    """CRUD operations for repository_progress."""

    async def create(self, run_id: UUID, repo_url: str) -> UUID:
        """Create a new repository progress entry."""
        entry_id = uuid4()
        await self._execute(
            """
            INSERT INTO rak.repository_progress (id, run_id, repo_url, status)
            VALUES (%s, %s, %s, 'pending')
            """,
            (entry_id, run_id, repo_url),
        )
        return entry_id

    async def update_status(self, entry_id: UUID, status: str) -> None:
        """Update the processing status."""
        await self._execute(
            "UPDATE rak.repository_progress SET status = %s WHERE id = %s",
            (status, entry_id),
        )

    async def set_pr_url(self, entry_id: UUID, pr_url: str) -> None:
        """Set the pull request URL."""
        await self._execute(
            "UPDATE rak.repository_progress SET pr_url = %s WHERE id = %s",
            (pr_url, entry_id),
        )

    async def set_error(self, entry_id: UUID, error: str) -> None:
        """Set the error message for a failed repository."""
        await self._execute(
            "UPDATE rak.repository_progress SET error = %s, status = 'failed' WHERE id = %s",
            (error, entry_id),
        )

    async def get_by_run(self, run_id: UUID) -> list[dict[str, Any]]:
        """Get all repository progress entries for a pipeline run."""
        return await self._fetch_all(
            "SELECT * FROM rak.repository_progress WHERE run_id = %s ORDER BY repo_url",
            (run_id,),
        )

    async def get_failed(self, run_id: UUID) -> list[dict[str, Any]]:
        """Get only failed repository entries for a run."""
        return await self._fetch_all(
            """
            SELECT * FROM rak.repository_progress
            WHERE run_id = %s AND status = 'failed'
            ORDER BY repo_url
            """,
            (run_id,),
        )

    async def count_by_status(self, run_id: UUID) -> dict[str, int]:
        """Get counts of repositories grouped by status."""
        rows = await self._fetch_all(
            """
            SELECT status, COUNT(*)::int AS count
            FROM rak.repository_progress
            WHERE run_id = %s
            GROUP BY status
            """,
            (run_id,),
        )
        return {row["status"]: row["count"] for row in rows}
