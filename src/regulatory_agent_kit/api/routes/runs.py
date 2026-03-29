"""Pipeline run status routes."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID  # noqa: TC003

from fastapi import APIRouter, Depends, HTTPException, status

from regulatory_agent_kit.api.dependencies import get_db_pool
from regulatory_agent_kit.models.pipeline import (
    ALL_STATUSES,
    PipelineStatus,
    PipelineStatusLiteral,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["runs"])

# ---------------------------------------------------------------------------
# In-memory fallback (used when DB is unavailable, e.g. in tests)
# ---------------------------------------------------------------------------

_runs: dict[UUID, PipelineStatus] = {}


def seed_run(run: PipelineStatus) -> None:
    """Seed a pipeline run into the in-memory store (test/demo helper)."""
    _runs[run.run_id] = run


def clear_runs() -> None:
    """Remove all seeded runs (test helper)."""
    _runs.clear()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get(
    "/runs/{run_id}",
    response_model=PipelineStatus,
    summary="Get pipeline run status",
)
async def get_run(
    run_id: UUID,
    db_pool: Any = Depends(get_db_pool),  # noqa: B008
) -> PipelineStatus:
    """Return the current status of a single pipeline run.

    Queries PostgreSQL when a DB pool is available, falls back to in-memory.
    """
    if db_pool is not None:
        return await _get_run_from_db(run_id, db_pool)

    run = _runs.get(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found.",
        )
    return run


@router.get(
    "/runs",
    response_model=list[PipelineStatus],
    summary="List pipeline runs",
)
async def list_runs(
    status_filter: PipelineStatusLiteral | None = None,
    db_pool: Any = Depends(get_db_pool),  # noqa: B008
) -> list[PipelineStatus]:
    """Return all known pipeline runs, optionally filtered by status.

    Queries PostgreSQL when a DB pool is available, falls back to in-memory.
    """
    if db_pool is not None:
        return await _list_runs_from_db(status_filter, db_pool)

    if status_filter is None:
        return list(_runs.values())
    return [run for run in _runs.values() if run.status == status_filter]


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


async def _get_run_from_db(run_id: UUID, db_pool: Any) -> PipelineStatus:
    """Query a single pipeline run from PostgreSQL with repo progress counts."""
    from regulatory_agent_kit.database.repositories.pipeline_runs import (
        PipelineRunRepository,
    )
    from regulatory_agent_kit.database.repositories.repository_progress import (
        RepositoryProgressRepository,
    )

    async with db_pool.connection() as conn:
        pipeline_repo = PipelineRunRepository(conn)
        run_info = await pipeline_repo.get(run_id)

        if run_info is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run {run_id} not found.",
            )

        progress_repo = RepositoryProgressRepository(conn)
        repo_counts = await progress_repo.count_by_status(run_id)

    return _row_to_pipeline_status(run_info, repo_counts)


async def _list_runs_from_db(
    status_filter: PipelineStatusLiteral | None,
    db_pool: Any,
) -> list[PipelineStatus]:
    """Query pipeline runs from PostgreSQL, optionally filtered by status."""
    from regulatory_agent_kit.database.repositories.pipeline_runs import (
        PipelineRunRepository,
    )

    async with db_pool.connection() as conn:
        pipeline_repo = PipelineRunRepository(conn)
        statuses = [status_filter] if status_filter is not None else list(ALL_STATUSES)
        rows: list[dict[str, Any]] = []
        for pipeline_status in statuses:
            rows.extend(await pipeline_repo.list_by_status(pipeline_status))

    return [_row_to_pipeline_status(row) for row in rows]


def _row_to_pipeline_status(
    row: dict[str, Any],
    repo_counts: dict[str, int] | None = None,
) -> PipelineStatus:
    """Convert a pipeline_runs DB row to a PipelineStatus model."""
    cost_summary: dict[str, Any] = {}
    if row.get("estimated_cost") is not None:
        cost_summary["estimated"] = float(row["estimated_cost"])
    if row.get("actual_cost") is not None:
        cost_summary["actual"] = float(row["actual_cost"])

    return PipelineStatus(
        run_id=row["run_id"],
        status=row["status"],
        phase=row.get("temporal_workflow_id", "") or "",
        repo_counts=repo_counts or {},
        cost_summary=cost_summary,
    )
