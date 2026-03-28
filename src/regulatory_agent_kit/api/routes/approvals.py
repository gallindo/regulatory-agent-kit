"""Approval checkpoint routes — human-in-the-loop decisions."""

from __future__ import annotations

from uuid import UUID  # noqa: TC003

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from regulatory_agent_kit.models.audit import CheckpointDecision  # noqa: TC001

router = APIRouter(tags=["approvals"])

# ---------------------------------------------------------------------------
# In-memory store (replaced by Temporal signals + DB in production)
# ---------------------------------------------------------------------------

# Maps run_id -> list of decisions received.
_pending_runs: dict[UUID, list[dict[str, str]]] = {}


def register_run(run_id: UUID) -> None:
    """Register a run as eligible for approval decisions.

    Called by the workflow starter or tests to seed known run IDs.
    """
    _pending_runs.setdefault(run_id, [])


def clear_runs() -> None:
    """Remove all registered runs (test helper)."""
    _pending_runs.clear()


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------


class ApprovalAck(BaseModel):
    """Acknowledgement of a recorded checkpoint decision."""

    run_id: str = Field(..., description="Pipeline run that received the decision.")
    status: str = Field(default="recorded", description="Status of the acknowledgement.")


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.post(
    "/approvals/{run_id}",
    response_model=ApprovalAck,
    status_code=status.HTTP_200_OK,
    summary="Submit a checkpoint decision",
)
async def submit_approval(run_id: UUID, decision: CheckpointDecision) -> ApprovalAck:
    """Record a human checkpoint decision for a pipeline run.

    Returns 404 when the *run_id* is not recognized.  In production
    this would signal the Temporal workflow to unblock.
    """
    if run_id not in _pending_runs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found.",
        )

    _pending_runs[run_id].append(
        {
            "checkpoint_type": decision.checkpoint_type,
            "decision": decision.decision,
            "actor": decision.actor,
        }
    )
    return ApprovalAck(run_id=str(run_id))
