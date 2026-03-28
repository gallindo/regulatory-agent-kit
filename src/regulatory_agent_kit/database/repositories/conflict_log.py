"""Repository for rak.conflict_log table."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from regulatory_agent_kit.database.repositories.base import BaseRepository


class ConflictLogRepository(BaseRepository):
    """CRUD operations for conflict_log."""

    async def create(
        self,
        run_id: UUID,
        conflicting_rules: list[dict[str, str]],
        affected_regions: list[dict[str, Any]],
    ) -> UUID:
        """Create a new conflict log entry."""
        conflict_id = uuid4()
        await self._execute(
            """
            INSERT INTO rak.conflict_log
                (id, run_id, conflicting_rules, affected_regions)
            VALUES (%s, %s, %s, %s)
            """,
            (conflict_id, run_id, conflicting_rules, affected_regions),
        )
        return conflict_id

    async def resolve(self, conflict_id: UUID, resolution: str, human_decision_id: UUID) -> None:
        """Mark a conflict as resolved with a human decision."""
        await self._execute(
            """
            UPDATE rak.conflict_log
            SET resolution = %s, human_decision_id = %s
            WHERE id = %s
            """,
            (resolution, human_decision_id, conflict_id),
        )

    async def get_by_run(self, run_id: UUID) -> list[dict[str, Any]]:
        """Get all conflicts for a pipeline run."""
        return await self._fetch_all(
            "SELECT * FROM rak.conflict_log WHERE run_id = %s ORDER BY detected_at",
            (run_id,),
        )

    async def get_unresolved(self, run_id: UUID) -> list[dict[str, Any]]:
        """Get unresolved conflicts for a pipeline run."""
        return await self._fetch_all(
            """
            SELECT * FROM rak.conflict_log
            WHERE run_id = %s AND resolution IS NULL
            ORDER BY detected_at
            """,
            (run_id,),
        )
