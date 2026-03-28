"""Pipeline run status routes."""

from __future__ import annotations

from uuid import UUID  # noqa: TC003

from fastapi import APIRouter, HTTPException, status

from regulatory_agent_kit.models.pipeline import (
    PipelineStatus,
    PipelineStatusLiteral,
)

router = APIRouter(tags=["runs"])

# ---------------------------------------------------------------------------
# In-memory store (replaced by Temporal queries + DB in production)
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
async def get_run(run_id: UUID) -> PipelineStatus:
    """Return the current status of a single pipeline run."""
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
) -> list[PipelineStatus]:
    """Return all known pipeline runs, optionally filtered by status."""
    if status_filter is None:
        return list(_runs.values())
    return [r for r in _runs.values() if r.status == status_filter]
