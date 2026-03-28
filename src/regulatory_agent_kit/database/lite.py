"""Lite Mode SQLite adapter — runs without PostgreSQL.

Provides simplified repository implementations backed by aiosqlite,
matching the same interface as the PostgreSQL repositories.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime  # noqa: TC003
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
"""


async def create_tables(db_path: str | Path) -> None:
    """Create all Lite Mode tables in the given SQLite database.

    Args:
        db_path: Path to the SQLite database file.
    """
    import aiosqlite

    async with aiosqlite.connect(str(db_path)) as db:
        await db.executescript(_SCHEMA_SQL)
        await db.commit()


# ---------------------------------------------------------------------------
# Lite repositories
# ---------------------------------------------------------------------------


class LitePipelineRunRepository:
    """Pipeline run CRUD backed by SQLite."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)

    async def create(
        self,
        regulation_id: str,
        total_repos: int,
        config_snapshot: dict[str, Any],
    ) -> UUID:
        """Create a new pipeline run and return its UUID."""
        import aiosqlite

        run_id = uuid4()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO pipeline_runs (run_id, regulation_id, status, total_repos,
                                           config_snapshot)
                VALUES (?, ?, 'pending', ?, ?)
                """,
                (str(run_id), regulation_id, total_repos, json.dumps(config_snapshot)),
            )
            await db.commit()
        return run_id

    async def get(self, run_id: UUID) -> dict[str, Any] | None:
        """Get a pipeline run by ID."""
        import aiosqlite

        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM pipeline_runs WHERE run_id = ?", (str(run_id),)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def update_status(self, run_id: UUID, status: str) -> None:
        """Update the lifecycle status of a pipeline run."""
        import aiosqlite

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE pipeline_runs SET status = ? WHERE run_id = ?",
                (status, str(run_id)),
            )
            await db.commit()


class LiteRepositoryProgressRepository:
    """Repository progress CRUD backed by SQLite."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)

    async def create(self, run_id: UUID, repo_url: str) -> UUID:
        """Create a new repository progress entry."""
        import aiosqlite

        entry_id = uuid4()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO repository_progress (id, run_id, repo_url, status)
                VALUES (?, ?, ?, 'pending')
                """,
                (str(entry_id), str(run_id), repo_url),
            )
            await db.commit()
        return entry_id

    async def update_status(self, entry_id: UUID, status: str) -> None:
        """Update the processing status."""
        import aiosqlite

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "UPDATE repository_progress SET status = ? WHERE id = ?",
                (status, str(entry_id)),
            )
            await db.commit()

    async def get_by_run(self, run_id: UUID) -> list[dict[str, Any]]:
        """Get all repository progress entries for a pipeline run."""
        import aiosqlite

        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM repository_progress WHERE run_id = ? ORDER BY repo_url",
                (str(run_id),),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]


class LiteAuditRepository:
    """Append-only audit entries backed by SQLite."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)

    async def insert(
        self,
        run_id: UUID,
        event_type: str,
        timestamp: datetime,
        payload: dict[str, Any],
        signature: str,
    ) -> UUID:
        """Insert a single audit entry."""
        import aiosqlite

        entry_id = uuid4()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO audit_entries (entry_id, run_id, event_type, timestamp,
                                           payload, signature)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(entry_id),
                    str(run_id),
                    event_type,
                    timestamp.isoformat(),
                    json.dumps(payload),
                    signature,
                ),
            )
            await db.commit()
        return entry_id

    async def get_by_run(self, run_id: UUID) -> list[dict[str, Any]]:
        """Get all audit entries for a pipeline run."""
        import aiosqlite

        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM audit_entries WHERE run_id = ? ORDER BY timestamp",
                (str(run_id),),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]


class LiteCheckpointDecisionRepository:
    """Checkpoint decisions backed by SQLite."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)

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
        import aiosqlite

        decision_id = uuid4()
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT INTO checkpoint_decisions
                    (id, run_id, checkpoint_type, actor, decision, rationale, signature)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(decision_id),
                    str(run_id),
                    checkpoint_type,
                    actor,
                    decision,
                    rationale,
                    signature,
                ),
            )
            await db.commit()
        return decision_id

    async def get_by_run(self, run_id: UUID) -> list[dict[str, Any]]:
        """Get all checkpoint decisions for a pipeline run."""
        import aiosqlite

        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM checkpoint_decisions WHERE run_id = ? ORDER BY decided_at",
                (str(run_id),),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_latest(self, run_id: UUID, checkpoint_type: str) -> dict[str, Any] | None:
        """Get the most recent decision for a given run and checkpoint type."""
        import aiosqlite

        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """
                SELECT * FROM checkpoint_decisions
                WHERE run_id = ? AND checkpoint_type = ?
                ORDER BY decided_at DESC, rowid DESC
                LIMIT 1
                """,
                (str(run_id), checkpoint_type),
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None
