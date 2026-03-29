"""Event ingestion route — receives regulatory events and starts pipelines."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from regulatory_agent_kit.api.dependencies import get_db_pool, get_temporal_client
from regulatory_agent_kit.models.events import RegulatoryEvent  # noqa: TC001

logger = logging.getLogger(__name__)

router = APIRouter(tags=["events"])


class EventAccepted(BaseModel):
    """Response body for a successfully accepted event."""

    workflow_id: str = Field(..., description="Identifier for the started pipeline workflow.")
    event_id: str = Field(..., description="Echo of the received event ID.")
    run_id: str = Field(default="", description="Pipeline run UUID (when DB is available).")


@router.post(
    "/events",
    response_model=EventAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a regulatory event",
)
async def submit_event(
    event: RegulatoryEvent,
    db_pool: Any = Depends(get_db_pool),  # noqa: B008
    temporal_client: Any = Depends(get_temporal_client),  # noqa: B008
) -> EventAccepted:
    """Validate and accept a regulatory event, starting a pipeline.

    Delegates persistence and workflow dispatch to the service layer.
    """
    from regulatory_agent_kit.api.services import (
        create_pipeline_run,
        start_temporal_workflow,
    )

    workflow_id = await start_temporal_workflow(temporal_client, event)
    run_id = await create_pipeline_run(
        db_pool, event.regulation_id, event.payload, workflow_id
    )

    return EventAccepted(
        workflow_id=workflow_id,
        event_id=str(event.event_id),
        run_id=run_id,
    )
