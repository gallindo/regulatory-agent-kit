"""Pipeline service layer — orchestrates persistence and workflow dispatch.

Extracted from route handlers to satisfy Single Responsibility and
Dependency Inversion principles: routes handle HTTP concerns only,
this service handles business logic with injected dependencies.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID, uuid4

logger = logging.getLogger(__name__)


async def create_pipeline_run(
    db_pool: Any,
    regulation_id: str,
    payload: dict[str, Any],
    workflow_id: str,
) -> str | None:
    """Create a pipeline_runs row and return the run UUID as a string.

    Returns ``None`` if the pool is unavailable or the insert fails.
    """
    if db_pool is None:
        return None
    try:
        from regulatory_agent_kit.database.repositories.pipeline_runs import (
            PipelineRunRepository,
        )

        async with db_pool.connection() as conn:
            repo = PipelineRunRepository(conn)
            run_uuid = await repo.create(
                regulation_id=regulation_id,
                total_repos=1,
                config_snapshot=payload,
                temporal_workflow_id=workflow_id,
            )
            return str(run_uuid)
    except (OSError, RuntimeError) as exc:
        logger.warning("Failed to persist pipeline run: %s", exc, exc_info=True)
        return None


async def start_temporal_workflow(
    temporal_client: Any,
    event: Any,
) -> str:
    """Start a Temporal workflow and return the workflow ID.

    Returns a generated ID if the client is unavailable.
    """
    workflow_id = f"rak-pipeline-{uuid4()}"
    if temporal_client is None:
        return workflow_id
    try:
        from regulatory_agent_kit.event_sources.starter import WorkflowStarter

        starter = WorkflowStarter(temporal_client)
        return await starter.start_pipeline(
            event=event,
            plugin={},
            config={"regulation_id": event.regulation_id},
        )
    except (OSError, RuntimeError, ConnectionError) as exc:
        logger.warning("Failed to start Temporal workflow: %s", exc, exc_info=True)
        return workflow_id


async def persist_approval(
    db_pool: Any,
    run_id: UUID,
    decision: Any,
) -> dict[str, Any] | None:
    """Validate run exists and persist a checkpoint decision.

    Returns the run_info dict on success, or ``None`` if the run is not found.
    """
    from regulatory_agent_kit.database.repositories.checkpoint_decisions import (
        CheckpointDecisionRepository,
    )
    from regulatory_agent_kit.database.repositories.pipeline_runs import (
        PipelineRunRepository,
    )

    async with db_pool.connection() as conn:
        pipeline_repo = PipelineRunRepository(conn)
        run_info = await pipeline_repo.get(run_id)
        if run_info is None:
            return None

        checkpoint_repo = CheckpointDecisionRepository(conn)
        await checkpoint_repo.create(
            run_id=run_id,
            checkpoint_type=decision.checkpoint_type,
            actor=decision.actor,
            decision=decision.decision,
            signature=decision.signature,
            rationale=decision.rationale,
            decided_at=decision.decided_at,
        )
    return run_info


async def signal_temporal_approval(
    temporal_client: Any,
    workflow_id: str,
    decision_summary: dict[str, str],
) -> None:
    """Signal a Temporal workflow with an approval decision."""
    if temporal_client is None or not workflow_id:
        return
    try:
        from regulatory_agent_kit.event_sources.starter import WorkflowStarter

        starter = WorkflowStarter(temporal_client)
        await starter.signal_approval(workflow_id, decision_summary)
    except (OSError, RuntimeError, ConnectionError) as exc:
        logger.warning(
            "Failed to signal Temporal workflow %s: %s",
            workflow_id,
            exc,
            exc_info=True,
        )
