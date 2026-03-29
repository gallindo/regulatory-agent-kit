"""Event ingestion route — receives regulatory events and starts pipelines."""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

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

    When a database pool is available, a ``pipeline_runs`` row is created.
    When a Temporal client is available, a workflow is started.
    Falls back to generating a workflow ID when services are unavailable.
    """
    workflow_id = f"rak-pipeline-{uuid4()}"
    run_id = ""

    # Persist the pipeline run in PostgreSQL if available
    if db_pool is not None:
        try:
            from regulatory_agent_kit.database.repositories.pipeline_runs import (
                PipelineRunRepository,
            )

            async with db_pool.connection() as conn:
                repo = PipelineRunRepository(conn)
                run_uuid = await repo.create(
                    regulation_id=event.regulation_id,
                    total_repos=1,
                    config_snapshot=event.payload,
                    temporal_workflow_id=workflow_id,
                )
                run_id = str(run_uuid)
                logger.info("Created pipeline run %s for event %s", run_id, event.event_id)
        except Exception:
            logger.warning("Failed to persist pipeline run", exc_info=True)

    # Start a Temporal workflow if the client is available
    if temporal_client is not None:
        try:
            from regulatory_agent_kit.event_sources.starter import WorkflowStarter

            starter = WorkflowStarter(temporal_client)
            workflow_id = await starter.start_pipeline(
                event=event,
                plugin={},
                config={"regulation_id": event.regulation_id},
            )
            logger.info("Started workflow %s for event %s", workflow_id, event.event_id)
        except Exception:
            logger.warning("Failed to start Temporal workflow", exc_info=True)

    return EventAccepted(
        workflow_id=workflow_id,
        event_id=str(event.event_id),
        run_id=run_id,
    )
