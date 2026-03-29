"""Approval checkpoint routes — human-in-the-loop decisions."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID  # noqa: TC003

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from regulatory_agent_kit.api.dependencies import get_db_pool, get_temporal_client
from regulatory_agent_kit.models.audit import CheckpointDecision  # noqa: TC001

logger = logging.getLogger(__name__)

router = APIRouter(tags=["approvals"])

# ---------------------------------------------------------------------------
# In-memory fallback (used when DB is unavailable, e.g. in tests)
# ---------------------------------------------------------------------------

_pending_runs: dict[UUID, list[dict[str, str]]] = {}


def register_run(run_id: UUID) -> None:
    """Register a run as eligible for approval decisions (test/demo helper)."""
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
async def submit_approval(
    run_id: UUID,
    decision: CheckpointDecision,
    db_pool: Any = Depends(get_db_pool),  # noqa: B008
    temporal_client: Any = Depends(get_temporal_client),  # noqa: B008
) -> ApprovalAck:
    """Record a human checkpoint decision for a pipeline run.

    Delegates persistence and Temporal signalling to the service layer.
    Falls back to in-memory storage when DB is unavailable.
    """
    if db_pool is not None:
        return await _handle_db_approval(run_id, decision, db_pool, temporal_client)

    # Fallback: in-memory store for tests
    if run_id not in _pending_runs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found.",
        )

    _pending_runs[run_id].append(decision.to_summary_dict())
    return ApprovalAck(run_id=str(run_id))


async def _handle_db_approval(
    run_id: UUID,
    decision: CheckpointDecision,
    db_pool: Any,
    temporal_client: Any,
) -> ApprovalAck:
    """Persist a decision to the database and optionally signal Temporal."""
    from regulatory_agent_kit.api.services import (
        persist_approval,
        signal_temporal_approval,
    )

    run_info = await persist_approval(db_pool, run_id, decision)
    if run_info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id} not found.",
        )

    temporal_workflow_id = run_info.get("temporal_workflow_id", "")
    await signal_temporal_approval(
        temporal_client, temporal_workflow_id, decision.to_summary_dict()
    )

    return ApprovalAck(run_id=str(run_id))
