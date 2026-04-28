"""Lite Mode SQLite adapter — runs without PostgreSQL.

Provides simplified repository implementations backed by aiosqlite,
matching the same interface as the PostgreSQL repositories.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path  # noqa: TC003
from typing import Any
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id          TEXT PRIMARY KEY,
    regulation_id   TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    total_repos     INTEGER NOT NULL DEFAULT 0,
    config_snapshot TEXT NOT NULL DEFAULT '{}',
    estimated_cost  REAL,
    actual_cost     REAL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at    TEXT
);

CREATE TABLE IF NOT EXISTS repository_progress (
    id       TEXT PRIMARY KEY,
    run_id   TEXT NOT NULL,
    repo_url TEXT NOT NULL,
    status   TEXT NOT NULL DEFAULT 'pending',
    pr_url   TEXT,
    error    TEXT,
    FOREIGN KEY (run_id) REFERENCES pipeline_runs(run_id)
);

CREATE TABLE IF NOT EXISTS audit_entries (
    entry_id   TEXT PRIMARY KEY,
    run_id     TEXT NOT NULL,
    event_type TEXT NOT NULL,
    timestamp  TEXT NOT NULL,
    payload    TEXT NOT NULL DEFAULT '{}',
    signature  TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (run_id) REFERENCES pipeline_runs(run_id)
);

CREATE TABLE IF NOT EXISTS checkpoint_decisions (
    id              TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL,
    checkpoint_type TEXT NOT NULL,
    actor           TEXT NOT NULL,
    decision        TEXT NOT NULL,
    rationale       TEXT,
    signature       TEXT NOT NULL DEFAULT '',
    decided_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (run_id) REFERENCES pipeline_runs(run_id)
);

CREATE TABLE IF NOT EXISTS file_analysis_cache (
    cache_key   TEXT PRIMARY KEY,
    repo_url    TEXT NOT NULL,
    file_path   TEXT NOT NULL,
    result      TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at  TEXT NOT NULL
);
"""


async def create_tables(db_path: str | Path) -> None:
    """Create all Lite Mode tables in the given SQLite database."""
    import aiosqlite

    async with aiosqlite.connect(str(db_path)) as db:
        await db.executescript(_SCHEMA_SQL)
        await db.commit()


# ---------------------------------------------------------------------------
# Base repository — eliminates repeated aiosqlite boilerplate
# ---------------------------------------------------------------------------


class _LiteRepository:
    """Base class for Lite Mode repositories.

    Provides helper methods that encapsulate the repeated
    connect → execute → commit/fetch pattern.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)

    async def _execute(self, query: str, params: tuple[Any, ...]) -> None:
        """Execute a write query (INSERT/UPDATE) with auto-commit."""
        import aiosqlite

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(query, params)
            await db.commit()

    async def _fetch_one(self, query: str, params: tuple[Any, ...]) -> dict[str, Any] | None:
        """Execute a query and return one row as a dict, or None."""
        import aiosqlite

        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def _fetch_all(self, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
        """Execute a query and return all rows as dicts."""
        import aiosqlite

        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def _insert_returning_id(self, query: str, params: tuple[Any, ...]) -> UUID:
        """Generate a UUID, execute an INSERT, and return the UUID."""
        new_id = uuid4()
        await self._execute(query, (str(new_id), *params))
        return new_id


# ---------------------------------------------------------------------------
# Lite repositories
# ---------------------------------------------------------------------------


class LitePipelineRunRepository(_LiteRepository):
    """Pipeline run CRUD backed by SQLite."""

    async def create(
        self,
        regulation_id: str,
        total_repos: int,
        config_snapshot: dict[str, Any],
    ) -> UUID:
        """Create a new pipeline run and return its UUID."""
        return await self._insert_returning_id(
            """
            INSERT INTO pipeline_runs
                (run_id, regulation_id, status, total_repos, config_snapshot)
            VALUES (?, ?, 'pending', ?, ?)
            """,
            (regulation_id, total_repos, json.dumps(config_snapshot)),
        )

    async def get(self, run_id: UUID) -> dict[str, Any] | None:
        """Get a pipeline run by ID."""
        return await self._fetch_one(
            "SELECT * FROM pipeline_runs WHERE run_id = ?", (str(run_id),)
        )

    async def update_status(self, run_id: UUID, status: str) -> None:
        """Update the lifecycle status of a pipeline run."""
        await self._execute(
            "UPDATE pipeline_runs SET status = ? WHERE run_id = ?",
            (status, str(run_id)),
        )


class LiteRepositoryProgressRepository(_LiteRepository):
    """Repository progress CRUD backed by SQLite."""

    async def create(self, run_id: UUID, repo_url: str) -> UUID:
        """Create a new repository progress entry."""
        return await self._insert_returning_id(
            """
            INSERT INTO repository_progress (id, run_id, repo_url, status)
            VALUES (?, ?, ?, 'pending')
            """,
            (str(run_id), repo_url),
        )

    async def update_status(self, entry_id: UUID, status: str) -> None:
        """Update the processing status."""
        await self._execute(
            "UPDATE repository_progress SET status = ? WHERE id = ?",
            (status, str(entry_id)),
        )

    async def get_by_run(self, run_id: UUID) -> list[dict[str, Any]]:
        """Get all repository progress entries for a pipeline run."""
        return await self._fetch_all(
            "SELECT * FROM repository_progress WHERE run_id = ? ORDER BY repo_url",
            (str(run_id),),
        )


class LiteAuditRepository(_LiteRepository):
    """Append-only audit entries backed by SQLite."""

    async def insert(
        self,
        run_id: UUID,
        event_type: str,
        timestamp: datetime,
        payload: dict[str, Any],
        signature: str,
    ) -> UUID:
        """Insert a single audit entry."""
        return await self._insert_returning_id(
            """
            INSERT INTO audit_entries
                (entry_id, run_id, event_type, timestamp, payload, signature)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (str(run_id), event_type, timestamp.isoformat(), json.dumps(payload), signature),
        )

    async def bulk_insert(self, entries: list[dict[str, Any]]) -> list[UUID]:
        """Insert multiple audit entries, returning their IDs."""
        ids: list[UUID] = []
        for entry in entries:
            entry_id = await self.insert(
                run_id=UUID(entry["run_id"])
                if isinstance(entry["run_id"], str)
                else entry["run_id"],
                event_type=entry["event_type"],
                timestamp=datetime.fromisoformat(entry["timestamp"])
                if isinstance(entry["timestamp"], str)
                else entry["timestamp"],
                payload=entry.get("payload", {}),
                signature=entry.get("signature", ""),
            )
            ids.append(entry_id)
        return ids

    async def get_by_run(self, run_id: UUID) -> list[dict[str, Any]]:
        """Get all audit entries for a pipeline run."""
        return await self._fetch_all(
            "SELECT * FROM audit_entries WHERE run_id = ? ORDER BY timestamp",
            (str(run_id),),
        )


class LiteCheckpointDecisionRepository(_LiteRepository):
    """Checkpoint decisions backed by SQLite."""

    async def create(
        self,
        run_id: UUID,
        checkpoint_type: str,
        actor: str,
        decision: str,
        signature: str,
        rationale: str | None = None,
    ) -> UUID:
        """Create a new checkpoint decision."""
        return await self._insert_returning_id(
            """
            INSERT INTO checkpoint_decisions
                (id, run_id, checkpoint_type, actor, decision, rationale, signature)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (str(run_id), checkpoint_type, actor, decision, rationale, signature),
        )

    async def get_by_run(self, run_id: UUID) -> list[dict[str, Any]]:
        """Get all checkpoint decisions for a pipeline run."""
        return await self._fetch_all(
            "SELECT * FROM checkpoint_decisions WHERE run_id = ? ORDER BY decided_at",
            (str(run_id),),
        )

    async def get_latest(self, run_id: UUID, checkpoint_type: str) -> dict[str, Any] | None:
        """Get the most recent decision for a given run and checkpoint type."""
        return await self._fetch_one(
            """
            SELECT * FROM checkpoint_decisions
            WHERE run_id = ? AND checkpoint_type = ?
            ORDER BY decided_at DESC, rowid DESC
            LIMIT 1
            """,
            (str(run_id), checkpoint_type),
        )


class LiteFileAnalysisCacheRepository(_LiteRepository):
    """File analysis cache backed by SQLite."""

    async def get(self, cache_key: str) -> dict[str, Any] | None:
        """Get a cached analysis result by key, ignoring expired entries."""
        return await self._fetch_one(
            """
            SELECT * FROM file_analysis_cache
            WHERE cache_key = ? AND expires_at > datetime('now')
            """,
            (cache_key,),
        )

    async def put(
        self,
        cache_key: str,
        repo_url: str,
        file_path: str,
        result: dict[str, Any],
        ttl_days: int = 7,
    ) -> None:
        """Insert or replace a cache entry with TTL-based expiration."""
        import aiosqlite

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO file_analysis_cache
                    (cache_key, repo_url, file_path, result, created_at, expires_at)
                VALUES (?, ?, ?, ?, datetime('now'),
                        datetime('now', '+' || ? || ' days'))
                """,
                (cache_key, repo_url, file_path, json.dumps(result), ttl_days),
            )
            await db.commit()

    async def delete_expired(self) -> int:
        """Delete expired cache entries, returning the count removed."""
        import aiosqlite

        async with aiosqlite.connect(self._db_path) as db:
            cursor = await db.execute(
                "DELETE FROM file_analysis_cache WHERE expires_at < datetime('now')"
            )
            count = cursor.rowcount
            await db.commit()
            return count
