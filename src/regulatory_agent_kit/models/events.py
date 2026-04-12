"""Regulatory event models — the triggers that start compliance pipelines."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class RegulatoryEvent(BaseModel):
    """A regulatory change event that triggers a compliance pipeline run.

    Produced by event sources (file watcher, webhook, Kafka, SQS) and consumed
    by the WorkflowStarter to initiate a Temporal workflow or Lite Mode run.
    """

    event_id: UUID = Field(default_factory=uuid4, description="Unique event identifier.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the event was created.",
    )
    regulation_id: str = Field(
        ...,
        min_length=1,
        description="ID of the regulation plugin (e.g., 'example-regulation-2025').",
    )
    change_type: Literal["new_requirement", "amendment", "withdrawal"] = Field(
        ...,
        description="Type of regulatory change.",
    )
    source: str = Field(
        ...,
        min_length=1,
        description="Origin of the event (e.g., 'webhook', 'file_watcher', 'kafka').",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Event-specific data.",
    )
