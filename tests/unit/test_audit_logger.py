"""Tests for the AuditLogger facade."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from regulatory_agent_kit.models.audit import AuditEntry
from regulatory_agent_kit.observability.audit_logger import (
    JSONLD_CONTEXT,
    JSONLD_TYPE_MAP,
    AuditLogger,
)

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture
def mock_repo() -> AsyncMock:
    """Fake AuditRepository that records calls."""
    repo = AsyncMock()
    repo.insert = AsyncMock(return_value=uuid4())
    return repo


@pytest.fixture
def mock_signer() -> MagicMock:
    """Fake AuditSigner that returns a deterministic signature."""
    signer = MagicMock()
    signer.sign.return_value = "c2lnbmVk"  # base64("signed")
    return signer


@pytest.fixture
def audit_logger(mock_repo: AsyncMock, mock_signer: MagicMock) -> AuditLogger:
    return AuditLogger(repo=mock_repo, signer=mock_signer)


@pytest.fixture
def run_id() -> UUID:
    return uuid4()


# ------------------------------------------------------------------
# Tests — all 9 event types produce the correct event_type
# ------------------------------------------------------------------


class TestAuditLoggerEventTypes:
    async def test_log_llm_call(
        self, audit_logger: AuditLogger, run_id: UUID, mock_repo: AsyncMock
    ) -> None:
        entry = await audit_logger.log_llm_call(run_id=run_id, payload={"model": "claude"})
        assert entry.event_type == "llm_call"
        mock_repo.insert.assert_awaited_once()

    async def test_log_tool_invocation(
        self, audit_logger: AuditLogger, run_id: UUID, mock_repo: AsyncMock
    ) -> None:
        entry = await audit_logger.log_tool_invocation(
            run_id=run_id, payload={"tool": "git_diff"}
        )
        assert entry.event_type == "tool_invocation"
        mock_repo.insert.assert_awaited_once()

    async def test_log_state_transition(
        self, audit_logger: AuditLogger, run_id: UUID, mock_repo: AsyncMock
    ) -> None:
        entry = await audit_logger.log_state_transition(
            run_id=run_id, payload={"from": "analyzing", "to": "refactoring"}
        )
        assert entry.event_type == "state_transition"
        mock_repo.insert.assert_awaited_once()

    async def test_log_human_decision(
        self, audit_logger: AuditLogger, run_id: UUID, mock_repo: AsyncMock
    ) -> None:
        entry = await audit_logger.log_human_decision(
            run_id=run_id, payload={"decision": "approved"}
        )
        assert entry.event_type == "human_decision"
        mock_repo.insert.assert_awaited_once()

    async def test_log_conflict_detected(
        self, audit_logger: AuditLogger, run_id: UUID, mock_repo: AsyncMock
    ) -> None:
        entry = await audit_logger.log_conflict_detected(
            run_id=run_id, payload={"conflicting_run": str(uuid4())}
        )
        assert entry.event_type == "conflict_detected"
        mock_repo.insert.assert_awaited_once()

    async def test_log_cost_estimation(
        self, audit_logger: AuditLogger, run_id: UUID, mock_repo: AsyncMock
    ) -> None:
        entry = await audit_logger.log_cost_estimation(
            run_id=run_id,
            payload={"estimated_total_cost_usd": 45.20, "repo_count": 50},
        )
        assert entry.event_type == "cost_estimation"
        mock_repo.insert.assert_awaited_once()

    async def test_log_test_execution(
        self, audit_logger: AuditLogger, run_id: UUID, mock_repo: AsyncMock
    ) -> None:
        entry = await audit_logger.log_test_execution(
            run_id=run_id,
            payload={"pass_rate": 0.95, "total_tests": 20},
        )
        assert entry.event_type == "test_execution"
        mock_repo.insert.assert_awaited_once()

    async def test_log_merge_request(
        self, audit_logger: AuditLogger, run_id: UUID, mock_repo: AsyncMock
    ) -> None:
        entry = await audit_logger.log_merge_request(
            run_id=run_id,
            payload={"pr_url": "https://github.com/org/repo/pull/42"},
        )
        assert entry.event_type == "merge_request"
        mock_repo.insert.assert_awaited_once()

    async def test_log_error(
        self, audit_logger: AuditLogger, run_id: UUID, mock_repo: AsyncMock
    ) -> None:
        entry = await audit_logger.log_error(
            run_id=run_id,
            payload={"message": "Agent timeout", "phase": "ANALYZING"},
        )
        assert entry.event_type == "error"
        mock_repo.insert.assert_awaited_once()


# ------------------------------------------------------------------
# Tests — JSON-LD enrichment
# ------------------------------------------------------------------


class TestJsonLdEnrichment:
    async def test_payload_has_context(
        self, audit_logger: AuditLogger, run_id: UUID
    ) -> None:
        entry = await audit_logger.log_llm_call(run_id=run_id, payload={"model": "claude"})
        assert entry.payload["@context"] == JSONLD_CONTEXT

    async def test_payload_has_type(
        self, audit_logger: AuditLogger, run_id: UUID
    ) -> None:
        entry = await audit_logger.log_llm_call(run_id=run_id, payload={"model": "claude"})
        assert entry.payload["@type"] == "LLMCall"

    async def test_all_event_types_get_correct_jsonld_type(
        self, audit_logger: AuditLogger, run_id: UUID
    ) -> None:
        """Every event type should map to its documented JSON-LD @type."""
        methods = {
            "llm_call": audit_logger.log_llm_call,
            "tool_invocation": audit_logger.log_tool_invocation,
            "state_transition": audit_logger.log_state_transition,
            "human_decision": audit_logger.log_human_decision,
            "conflict_detected": audit_logger.log_conflict_detected,
            "cost_estimation": audit_logger.log_cost_estimation,
            "test_execution": audit_logger.log_test_execution,
            "merge_request": audit_logger.log_merge_request,
            "error": audit_logger.log_error,
        }
        for event_type, method in methods.items():
            entry = await method(run_id=run_id, payload={"test": True})
            assert entry.payload["@context"] == JSONLD_CONTEXT
            assert entry.payload["@type"] == JSONLD_TYPE_MAP[event_type]

    async def test_caller_fields_preserved(
        self, audit_logger: AuditLogger, run_id: UUID
    ) -> None:
        payload = {"model": "claude", "cost_usd": 0.042, "agent": "analyzer"}
        entry = await audit_logger.log_llm_call(run_id=run_id, payload=payload)
        assert entry.payload["model"] == "claude"
        assert entry.payload["cost_usd"] == 0.042
        assert entry.payload["agent"] == "analyzer"

    async def test_caller_context_not_overwritten(
        self, audit_logger: AuditLogger, run_id: UUID
    ) -> None:
        payload = {"@context": "https://custom.org", "model": "claude"}
        entry = await audit_logger.log_llm_call(run_id=run_id, payload=payload)
        assert entry.payload["@context"] == "https://custom.org"

    async def test_caller_type_not_overwritten(
        self, audit_logger: AuditLogger, run_id: UUID
    ) -> None:
        payload = {"@type": "CustomType", "model": "claude"}
        entry = await audit_logger.log_llm_call(run_id=run_id, payload=payload)
        assert entry.payload["@type"] == "CustomType"


# ------------------------------------------------------------------
# Tests — signature is always present
# ------------------------------------------------------------------


class TestAuditLoggerSignature:
    async def test_entries_have_nonempty_signature(
        self, audit_logger: AuditLogger, run_id: UUID
    ) -> None:
        entry = await audit_logger.log_llm_call(run_id=run_id, payload={"model": "gpt-4"})
        assert entry.signature != ""
        assert len(entry.signature) > 0

    async def test_signer_called_with_enriched_payload(
        self,
        audit_logger: AuditLogger,
        run_id: UUID,
        mock_signer: MagicMock,
    ) -> None:
        """Signer receives the JSON-LD enriched payload, not the raw caller payload."""
        payload: dict[str, Any] = {"key": "value"}
        await audit_logger.log_tool_invocation(run_id=run_id, payload=payload)
        signed_payload = mock_signer.sign.call_args[0][0]
        assert signed_payload["@context"] == JSONLD_CONTEXT
        assert signed_payload["@type"] == "ToolInvocation"
        assert signed_payload["key"] == "value"

    async def test_entry_is_audit_entry_model(
        self, audit_logger: AuditLogger, run_id: UUID
    ) -> None:
        entry = await audit_logger.log_state_transition(
            run_id=run_id, payload={"state": "done"}
        )
        assert isinstance(entry, AuditEntry)
        assert entry.run_id == run_id
