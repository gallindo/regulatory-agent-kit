"""Repository for rak.pipeline_runs table."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from regulatory_agent_kit.database.repositories.base import BaseRepository


class PipelineRunRepository(BaseRepository):
    """CRUD operations for pipeline_runs."""

    async def create(
        self,
        regulation_id: str,
        total_repos: int,
        config_snapshot: dict[str, Any],
        temporal_workflow_id: str | None = None,
    ) -> UUID:
        """Create a new pipeline run, returning its UUID."""
        run_id = uuid4()
        await self._execute(
            """
            INSERT INTO rak.pipeline_runs
                (run_id, regulation_id, status, total_repos, config_snapshot, temporal_workflow_id)
            VALUES (%s, %s, 'pending', %s, %s, %s)
            """,
            (run_id, regulation_id, total_repos, config_snapshot, temporal_workflow_id),
        )
        return run_id

    async def get(self, run_id: UUID) -> dict[str, Any] | None:
        """Get a pipeline run by ID."""
        return await self._fetch_one(
            "SELECT * FROM rak.pipeline_runs WHERE run_id = %s", (run_id,)
        )

    async def update_status(self, run_id: UUID, status: str) -> None:
        """Update the lifecycle status of a pipeline run."""
        await self._execute(
            "UPDATE rak.pipeline_runs SET status = %s WHERE run_id = %s",
            (status, run_id),
        )

    async def update_cost(
        self, run_id: UUID, estimated_cost: float | None = None, actual_cost: float | None = None
    ) -> None:
        """Update cost fields on a pipeline run."""
        if estimated_cost is not None:
            await self._execute(
                "UPDATE rak.pipeline_runs SET estimated_cost = %s WHERE run_id = %s",
                (estimated_cost, run_id),
            )
        if actual_cost is not None:
            await self._execute(
                "UPDATE rak.pipeline_runs SET actual_cost = %s WHERE run_id = %s",
                (actual_cost, run_id),
            )

    async def complete(self, run_id: UUID, status: str) -> None:
        """Mark a pipeline run as terminal with completed_at timestamp."""
        await self._execute(
            """
            UPDATE rak.pipeline_runs
            SET status = %s, completed_at = %s
            WHERE run_id = %s
            """,
            (status, datetime.now(UTC), run_id),
        )

    async def list_by_status(self, status: str) -> list[dict[str, Any]]:
        """List pipeline runs filtered by status."""
        return await self._fetch_all(
            "SELECT * FROM rak.pipeline_runs WHERE status = %s ORDER BY created_at DESC",
            (status,),
        )

    async def list_by_regulation(self, regulation_id: str) -> list[dict[str, Any]]:
        """List pipeline runs for a specific regulation."""
        return await self._fetch_all(
            "SELECT * FROM rak.pipeline_runs WHERE regulation_id = %s ORDER BY created_at DESC",
            (regulation_id,),
        )
