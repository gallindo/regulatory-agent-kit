"""Repository for rak.audit_entries table — append-only."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from typing import Any
from uuid import UUID, uuid4

from regulatory_agent_kit.database.repositories.base import BaseRepository


class AuditRepository(BaseRepository):
    """INSERT and SELECT only — audit_entries is append-only by design."""

    async def insert(
        self,
        run_id: UUID,
        event_type: str,
        timestamp: datetime,
        payload: dict[str, Any],
        signature: str,
    ) -> UUID:
        """Insert a single audit entry."""
        entry_id = uuid4()
        await self._execute(
            """
            INSERT INTO rak.audit_entries
                (entry_id, run_id, event_type, timestamp, payload, signature)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (entry_id, run_id, event_type, timestamp, payload, signature),
        )
        return entry_id

    async def bulk_insert(self, entries: list[dict[str, Any]]) -> list[UUID]:
        """Insert multiple audit entries, returning their IDs."""
        ids: list[UUID] = []
        for entry in entries:
            entry_id = uuid4()
            await self._execute(
                """
                INSERT INTO rak.audit_entries
                    (entry_id, run_id, event_type, timestamp, payload, signature)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    entry_id,
                    entry["run_id"],
                    entry["event_type"],
                    entry["timestamp"],
                    entry["payload"],
                    entry["signature"],
                ),
            )
            ids.append(entry_id)
        return ids

    async def get_by_run(self, run_id: UUID) -> list[dict[str, Any]]:
        """Get all audit entries for a pipeline run."""
        return await self._fetch_all(
            "SELECT * FROM rak.audit_entries WHERE run_id = %s ORDER BY timestamp",
            (run_id,),
        )

    async def get_by_type(self, run_id: UUID, event_type: str) -> list[dict[str, Any]]:
        """Get audit entries filtered by event type."""
        return await self._fetch_all(
            """
            SELECT * FROM rak.audit_entries
            WHERE run_id = %s AND event_type = %s
            ORDER BY timestamp
            """,
            (run_id, event_type),
        )

    async def get_by_date_range(self, start: datetime, end: datetime) -> list[dict[str, Any]]:
        """Get audit entries within a date range."""
        return await self._fetch_all(
            """
            SELECT * FROM rak.audit_entries
            WHERE timestamp >= %s AND timestamp < %s
            ORDER BY timestamp
            """,
            (start, end),
        )
