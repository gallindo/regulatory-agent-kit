"""Audit trail and checkpoint decision models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

# The 9 audit event types defined in data-model.md Section 3.3
AuditEventType = Literal[
    "llm_call",
    "tool_invocation",
    "state_transition",
    "human_decision",
    "conflict_detected",
    "cost_estimation",
    "test_execution",
    "merge_request",
    "error",
]

CheckpointType = Literal["impact_review", "merge_review"]

DecisionType = Literal["approved", "rejected", "modifications_requested"]


class AuditEntry(BaseModel):
    """An immutable, cryptographically signed audit trail entry.

    Corresponds to one row in the partitioned ``rak.audit_entries`` table.
    """

    entry_id: UUID = Field(default_factory=uuid4, description="Unique entry identifier.")
    run_id: UUID = Field(..., description="Pipeline run this entry belongs to.")
    event_type: AuditEventType = Field(..., description="Category of audited event.")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the event occurred.",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict, description="Event-specific data (JSON-LD format)."
    )
    signature: str = Field(
        default="", description="Ed25519 signature over the canonicalized payload (Base64)."
    )


class CheckpointDecision(BaseModel):
    """A human approval or rejection at a pipeline checkpoint.

    Includes ``checkpoint_type`` to identify which gate this decision applies to,
    even though the LLD Section 2.1 class diagram omits it — the field is required
    by the Temporal signal handler, API endpoint, and database DTO.
    """

    checkpoint_type: CheckpointType = Field(
        ..., description="Which checkpoint gate: impact_review or merge_review."
    )
    actor: str = Field(..., min_length=1, description="Human identity (email or SSO ID).")
    decision: DecisionType = Field(
        ..., description="The decision: approved, rejected, or modifications_requested."
    )
    rationale: str | None = Field(
        default=None, description="Optional explanation for the decision."
    )
    signature: str = Field(default="", description="Ed25519 signature over the decision payload.")
    decided_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When the decision was made.",
    )
