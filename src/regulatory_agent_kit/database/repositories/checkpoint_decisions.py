"""Repository for rak.checkpoint_decisions table."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from typing import Any
from uuid import UUID, uuid4

from regulatory_agent_kit.database.repositories.base import BaseRepository


class CheckpointDecisionRepository(BaseRepository):
    """CRUD operations for checkpoint_decisions."""

    async def create(
        self,
        run_id: UUID,
        checkpoint_type: str,
        actor: str,
        decision: str,
        signature: str,
        rationale: str | None = None,
        decided_at: datetime | None = None,
    ) -> UUID:
        """Create a new checkpoint decision."""
        decision_id = uuid4()
        await self._execute(
            """
            INSERT INTO rak.checkpoint_decisions
                (id, run_id, checkpoint_type, actor, decision, rationale, signature, decided_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, COALESCE(%s, now()))
            """,
            (
                decision_id,
                run_id,
                checkpoint_type,
                actor,
                decision,
                rationale,
                signature,
                decided_at,
            ),
        )
        return decision_id

    async def get_by_run(self, run_id: UUID) -> list[dict[str, Any]]:
        """Get all checkpoint decisions for a pipeline run."""
        return await self._fetch_all(
            "SELECT * FROM rak.checkpoint_decisions WHERE run_id = %s ORDER BY decided_at",
            (run_id,),
        )

    async def get_latest(self, run_id: UUID, checkpoint_type: str) -> dict[str, Any] | None:
        """Get the most recent decision for a given run and checkpoint type."""
        return await self._fetch_one(
            """
            SELECT * FROM rak.checkpoint_decisions
            WHERE run_id = %s AND checkpoint_type = %s
            ORDER BY decided_at DESC
            LIMIT 1
            """,
            (run_id, checkpoint_type),
        )
