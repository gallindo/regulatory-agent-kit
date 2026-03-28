"""Event ingestion route — receives regulatory events and starts pipelines."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from regulatory_agent_kit.models.events import RegulatoryEvent  # noqa: TC001

router = APIRouter(tags=["events"])


class EventAccepted(BaseModel):
    """Response body for a successfully accepted event."""

    workflow_id: str = Field(..., description="Identifier for the started pipeline workflow.")
    event_id: str = Field(..., description="Echo of the received event ID.")


@router.post(
    "/events",
    response_model=EventAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a regulatory event",
)
async def submit_event(event: RegulatoryEvent) -> EventAccepted:
    """Validate and accept a regulatory event, returning a workflow ID.

    In a full deployment the handler would forward the event to
    Temporal via the ``WorkflowStarter``.  For now it returns a
    deterministic workflow ID so callers can correlate later.
    """
    workflow_id = f"rak-pipeline-{uuid4()}"
    return EventAccepted(
        workflow_id=workflow_id,
        event_id=str(event.event_id),
    )
