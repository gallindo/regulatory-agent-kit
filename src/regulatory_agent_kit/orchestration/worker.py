"""Temporal worker setup — registers all workflows and activities."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from temporalio.worker import Worker

from regulatory_agent_kit.orchestration.activities import ALL_ACTIVITIES
from regulatory_agent_kit.orchestration.workflows import ALL_WORKFLOWS

if TYPE_CHECKING:
    from temporalio.client import Client

    from regulatory_agent_kit.config import Settings

logger = logging.getLogger(__name__)

DEFAULT_TASK_QUEUE = "rak-pipeline"


def _build_otel_interceptors() -> list[Any]:
    """Build OpenTelemetry tracing interceptors for the Temporal worker.

    Returns:
        A list containing a ``TracingInterceptor`` if the
        ``temporalio.contrib.opentelemetry`` package is available,
        or an empty list otherwise.
    """
    try:
        from temporalio.contrib.opentelemetry import TracingInterceptor

        interceptor = TracingInterceptor()
        logger.info("Temporal OpenTelemetry TracingInterceptor enabled")
        return [interceptor]
    except ImportError:
        logger.warning(
            "temporalio.contrib.opentelemetry not available — skipping Temporal OTel interceptor"
        )
        return []


def create_worker(
    client: Client,
    task_queue: str = DEFAULT_TASK_QUEUE,
    *,
    enable_otel: bool = True,
) -> Worker:
    """Create a Temporal Worker registered with all workflows and activities.

    Args:
        client: Connected Temporal client.
        task_queue: Temporal task queue name.
        enable_otel: Whether to attach OpenTelemetry tracing interceptors.

    Returns:
        A configured ``Worker`` ready to be run.
    """
    interceptors = _build_otel_interceptors() if enable_otel else []

    return Worker(
        client,
        task_queue=task_queue,
        workflows=ALL_WORKFLOWS,
        activities=ALL_ACTIVITIES,
        interceptors=interceptors,
    )


async def run_worker(settings: Settings) -> None:
    """Connect to Temporal and run a worker until interrupted.

    Args:
        settings: Application settings containing Temporal connection info.
    """
    from temporalio.client import Client

    logger.info(
        "Connecting to Temporal at %s (namespace=%s, queue=%s)",
        settings.temporal.address,
        settings.temporal.namespace,
        settings.temporal.task_queue,
    )

    client = await Client.connect(
        settings.temporal.address,
        namespace=settings.temporal.namespace,
    )

    worker = create_worker(client, task_queue=settings.temporal.task_queue)
    logger.info("Starting Temporal worker on queue %s", settings.temporal.task_queue)
    await worker.run()
