"""Tests for the AuditLogger facade (Phase 8)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from regulatory_agent_kit.models.audit import AuditEntry
from regulatory_agent_kit.observability.audit_logger import AuditLogger

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
# Tests — each log method produces the correct event_type
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
        entry = await audit_logger.log_tool_invocation(run_id=run_id, payload={"tool": "git_diff"})
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

    async def test_signer_called_with_payload(
        self,
        audit_logger: AuditLogger,
        run_id: UUID,
        mock_signer: MagicMock,
    ) -> None:
        payload: dict[str, Any] = {"key": "value"}
        await audit_logger.log_tool_invocation(run_id=run_id, payload=payload)
        mock_signer.sign.assert_called_once_with(payload)

    async def test_entry_is_audit_entry_model(
        self, audit_logger: AuditLogger, run_id: UUID
    ) -> None:
        entry = await audit_logger.log_state_transition(run_id=run_id, payload={"state": "done"})
        assert isinstance(entry, AuditEntry)
        assert entry.run_id == run_id
