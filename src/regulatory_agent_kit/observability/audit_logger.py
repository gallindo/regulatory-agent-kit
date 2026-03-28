"""High-level audit logger — creates, signs, and persists audit trail entries."""

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


class AuditLogger:
    """Facade that creates, signs, and persists ``AuditEntry`` records.

    Each ``log_*`` helper maps to one of the nine audit event types defined
    in ``models.audit.AuditEventType``.
    """

    def __init__(self, repo: AuditRepository, signer: AuditSigner) -> None:
        self._repo = repo
        self._signer = signer

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _persist(
        self,
        run_id: UUID,
        event_type: AuditEventType,
        payload: dict[str, Any],
    ) -> AuditEntry:
        """Build an entry, sign it, and write it to the database."""
        entry = AuditEntry(run_id=run_id, event_type=event_type, payload=payload)
        entry.signature = self._signer.sign(payload)

        await self._repo.insert(
            run_id=entry.run_id,
            event_type=entry.event_type,
            timestamp=entry.timestamp,
            payload=entry.payload,
            signature=entry.signature,
        )
        logger.debug("Audit entry persisted: %s / %s", event_type, entry.entry_id)
        return entry

    # ------------------------------------------------------------------
    # Public log methods
    # ------------------------------------------------------------------

    async def log_llm_call(self, *, run_id: UUID, payload: dict[str, Any]) -> AuditEntry:
        """Record an LLM invocation."""
        return await self._persist(run_id, "llm_call", payload)

    async def log_tool_invocation(self, *, run_id: UUID, payload: dict[str, Any]) -> AuditEntry:
        """Record a tool invocation by an agent."""
        return await self._persist(run_id, "tool_invocation", payload)

    async def log_state_transition(self, *, run_id: UUID, payload: dict[str, Any]) -> AuditEntry:
        """Record a pipeline state transition."""
        return await self._persist(run_id, "state_transition", payload)

    async def log_human_decision(self, *, run_id: UUID, payload: dict[str, Any]) -> AuditEntry:
        """Record a human checkpoint decision."""
        return await self._persist(run_id, "human_decision", payload)

    async def log_conflict_detected(self, *, run_id: UUID, payload: dict[str, Any]) -> AuditEntry:
        """Record a detected conflict between concurrent pipeline runs."""
        return await self._persist(run_id, "conflict_detected", payload)
