"""WorkflowStarter — wraps the Temporal client for pipeline lifecycle management."""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from temporalio.client import Client, WorkflowExecutionStatus

from regulatory_agent_kit.exceptions import EventSourceError
from regulatory_agent_kit.models.events import RegulatoryEvent  # noqa: TC001

logger = logging.getLogger(__name__)

# Workflow class name as string — avoids importing the actual workflow module
# which may have heavy dependencies.
_WORKFLOW_NAME = "CompliancePipelineWorkflow"
_TASK_QUEUE = "rak-pipeline"


class WorkflowStarter:
    """Thin wrapper around the Temporal Python SDK client.

    Provides convenience methods for starting, signalling, querying,
    cancelling, and listing compliance-pipeline workflows.
    """

    def __init__(self, client: Client, *, task_queue: str = _TASK_QUEUE) -> None:
        self._client = client
        self._task_queue = task_queue

    async def start_pipeline(
        self,
        event: RegulatoryEvent,
        plugin: dict[str, Any],
        config: dict[str, Any],
    ) -> str:
        """Start a new compliance-pipeline workflow and return its ID.

        Args:
            event: The regulatory event that triggered the pipeline.
            plugin: Serialized regulation plugin data.
            config: Pipeline configuration dict.

        Returns:
            The Temporal workflow ID.
        """
        workflow_id = f"rak-pipeline-{uuid4()}"
        try:
            await self._client.start_workflow(
                _WORKFLOW_NAME,
                args=[event.model_dump(mode="json"), plugin, config],
                id=workflow_id,
                task_queue=self._task_queue,
            )
        except Exception as exc:
            msg = f"Failed to start pipeline workflow: {exc}"
            raise EventSourceError(msg) from exc
        logger.info("Started workflow %s for event %s", workflow_id, event.event_id)
        return workflow_id

    async def signal_approval(
        self,
        workflow_id: str,
        decision: dict[str, Any],
    ) -> None:
        """Send an approval / rejection signal to a running workflow.

        Args:
            workflow_id: The Temporal workflow ID.
            decision: Decision payload (e.g. ``{"approved": True}``).
        """
        try:
            handle = self._client.get_workflow_handle(workflow_id)
            await handle.signal("approval", decision)
        except Exception as exc:
            msg = f"Failed to signal workflow {workflow_id}: {exc}"
            raise EventSourceError(msg) from exc

    async def query_status(self, workflow_id: str) -> dict[str, Any]:
        """Query the current status of a workflow.

        Args:
            workflow_id: The Temporal workflow ID.

        Returns:
            Status dict from the workflow query handler.
        """
        try:
            handle = self._client.get_workflow_handle(workflow_id)
            result: dict[str, Any] = await handle.query("status")
        except Exception as exc:
            msg = f"Failed to query workflow {workflow_id}: {exc}"
            raise EventSourceError(msg) from exc
        return result

    async def cancel(self, workflow_id: str) -> None:
        """Request cancellation of a running workflow.

        Args:
            workflow_id: The Temporal workflow ID.
        """
        try:
            handle = self._client.get_workflow_handle(workflow_id)
            await handle.cancel()
        except Exception as exc:
            msg = f"Failed to cancel workflow {workflow_id}: {exc}"
            raise EventSourceError(msg) from exc

    async def list_running(self) -> list[str]:
        """Return workflow IDs of all currently running pipelines.

        Returns:
            List of workflow IDs with ``RUNNING`` status.
        """
        running: list[str] = []
        try:
            async for workflow in self._client.list_workflows(
                query=(
                    f"WorkflowType = '{_WORKFLOW_NAME}' "
                    f"AND ExecutionStatus = '{WorkflowExecutionStatus.RUNNING.name}'"
                ),
            ):
                running.append(workflow.id)
        except Exception as exc:
            msg = f"Failed to list running workflows: {exc}"
            raise EventSourceError(msg) from exc
        return running
