"""High-level audit logger — creates, signs, and persists audit trail entries.

All payloads are enriched with JSON-LD ``@context`` and ``@type`` fields
as specified in data-model.md Section 5, giving each event a
self-describing schema for cross-system compatibility.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID  # noqa: TC003

from regulatory_agent_kit.database.repositories.audit_entries import (
    AuditRepository,  # noqa: TC001
)
from regulatory_agent_kit.models.audit import AuditEntry, AuditEventType
from regulatory_agent_kit.util.crypto import AuditSigner  # noqa: TC001

logger = logging.getLogger(__name__)

# JSON-LD context URI used for all audit payloads.
JSONLD_CONTEXT = "https://schema.org"

# Maps each event_type to its JSON-LD @type as defined in data-model.md Section 5.
JSONLD_TYPE_MAP: dict[str, str] = {
    "llm_call": "LLMCall",
    "tool_invocation": "ToolInvocation",
    "state_transition": "StateTransition",
    "human_decision": "HumanDecision",
    "conflict_detected": "ConflictDetected",
    "cost_estimation": "CostEstimation",
    "test_execution": "TestExecution",
    "merge_request": "MergeRequest",
    "error": "Error",
}


class AuditLogger:
    """Facade that creates, signs, and persists ``AuditEntry`` records.

    Each ``log_*`` helper maps to one of the nine audit event types defined
    in ``models.audit.AuditEventType``.  All payloads are enriched with
    JSON-LD ``@context`` and ``@type`` fields before signing and storage.
    """

    def __init__(self, repo: AuditRepository, signer: AuditSigner) -> None:
        self._repo = repo
        self._signer = signer

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _enrich_payload(event_type: AuditEventType, payload: dict[str, Any]) -> dict[str, Any]:
        """Add JSON-LD ``@context`` and ``@type`` fields to the payload.

        Caller-provided fields are preserved; JSON-LD fields are prepended.
        If the caller already set ``@context`` or ``@type``, those values
        are respected (no overwrite).
        """
        enriched: dict[str, Any] = {}
        if "@context" not in payload:
            enriched["@context"] = JSONLD_CONTEXT
        if "@type" not in payload:
            enriched["@type"] = JSONLD_TYPE_MAP.get(event_type, event_type)
        enriched.update(payload)
        return enriched

    async def _persist(
        self,
        run_id: UUID,
        event_type: AuditEventType,
        payload: dict[str, Any],
    ) -> AuditEntry:
        """Enrich payload with JSON-LD, sign, and write to the database."""
        enriched = self._enrich_payload(event_type, payload)
        entry = AuditEntry(run_id=run_id, event_type=event_type, payload=enriched)
        entry.signature = self._signer.sign(enriched)
        await self._insert_entry(entry)
        logger.debug("Audit entry persisted: %s / %s", event_type, entry.entry_id)
        return entry

    async def _insert_entry(self, entry: AuditEntry) -> None:
        """Persist a single audit entry — encapsulates field unpacking."""
        await self._repo.insert(
            run_id=entry.run_id,
            event_type=entry.event_type,
            timestamp=entry.timestamp,
            payload=entry.payload,
            signature=entry.signature,
        )

    # ------------------------------------------------------------------
    # Public log methods — one per event type
    # ------------------------------------------------------------------

    async def log_llm_call(self, *, run_id: UUID, payload: dict[str, Any]) -> AuditEntry:
        """Record an LLM invocation (data-model.md Section 5.1)."""
        return await self._persist(run_id, "llm_call", payload)

    async def log_tool_invocation(self, *, run_id: UUID, payload: dict[str, Any]) -> AuditEntry:
        """Record a tool invocation by an agent (data-model.md Section 5.2)."""
        return await self._persist(run_id, "tool_invocation", payload)

    async def log_state_transition(self, *, run_id: UUID, payload: dict[str, Any]) -> AuditEntry:
        """Record a pipeline state transition (data-model.md Section 5.3)."""
        return await self._persist(run_id, "state_transition", payload)

    async def log_human_decision(self, *, run_id: UUID, payload: dict[str, Any]) -> AuditEntry:
        """Record a human checkpoint decision (data-model.md Section 5.4)."""
        return await self._persist(run_id, "human_decision", payload)

    async def log_conflict_detected(
        self, *, run_id: UUID, payload: dict[str, Any]
    ) -> AuditEntry:
        """Record a cross-regulation conflict (data-model.md Section 5.5)."""
        return await self._persist(run_id, "conflict_detected", payload)

    async def log_cost_estimation(self, *, run_id: UUID, payload: dict[str, Any]) -> AuditEntry:
        """Record a pre-run cost estimate (data-model.md Section 5.6)."""
        return await self._persist(run_id, "cost_estimation", payload)

    async def log_test_execution(self, *, run_id: UUID, payload: dict[str, Any]) -> AuditEntry:
        """Record a test execution result (data-model.md Section 5.7)."""
        return await self._persist(run_id, "test_execution", payload)

    async def log_merge_request(self, *, run_id: UUID, payload: dict[str, Any]) -> AuditEntry:
        """Record a merge request creation (data-model.md Section 5.8)."""
        return await self._persist(run_id, "merge_request", payload)

    async def log_error(self, *, run_id: UUID, payload: dict[str, Any]) -> AuditEntry:
        """Record an error event."""
        return await self._persist(run_id, "error", payload)
