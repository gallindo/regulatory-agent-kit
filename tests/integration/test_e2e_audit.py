"""E2E tests for the audit trail system.

Covers Ed25519 signing, AuditLogger event persistence,
Write-Ahead Log replay, corruption recovery, and local archival export.
"""

from __future__ import annotations

import json
from pathlib import Path  # noqa: TC003
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from regulatory_agent_kit.observability.audit_logger import AuditLogger
from regulatory_agent_kit.observability.storage import AuditArchiver
from regulatory_agent_kit.observability.wal import WriteAheadLog
from regulatory_agent_kit.util.crypto import AuditSigner


@pytest.mark.integration
class TestE2EAuditTrail:
    """End-to-end tests for the audit trail subsystem."""

    async def test_sign_verify_round_trip(self, tmp_path: Path) -> None:
        """Generate key, sign payload, verify, tamper, verify fails."""
        private_pem, _public_pem = AuditSigner.generate_key_pair()
        signer = AuditSigner.from_private_bytes(private_pem)

        payload = {"action": "deploy", "version": "1.2.3"}
        signature = signer.sign(payload)

        assert signer.verify(payload, signature) is True

        # Tamper with the payload — verification must fail.
        tampered = {**payload, "version": "9.9.9"}
        assert signer.verify(tampered, signature) is False

    async def test_audit_logger_persists_all_event_types(self, tmp_path: Path) -> None:
        """All 5 AuditLogger methods produce entries with correct event_type."""
        mock_repo = AsyncMock()
        mock_repo.insert = AsyncMock()

        private_pem, _ = AuditSigner.generate_key_pair()
        signer = AuditSigner.from_private_bytes(private_pem)

        audit_logger = AuditLogger(repo=mock_repo, signer=signer)
        run_id = uuid4()

        await audit_logger.log_llm_call(run_id=run_id, payload={"model": "test"})
        await audit_logger.log_tool_invocation(run_id=run_id, payload={"tool": "git"})
        await audit_logger.log_state_transition(run_id=run_id, payload={"phase": "ANALYZING"})
        await audit_logger.log_human_decision(run_id=run_id, payload={"decision": "approved"})
        await audit_logger.log_conflict_detected(run_id=run_id, payload={"conflict": "merge"})

        assert mock_repo.insert.await_count == 5

        expected_types = {
            "llm_call",
            "tool_invocation",
            "state_transition",
            "human_decision",
            "conflict_detected",
        }
        actual_types = set()
        for call in mock_repo.insert.call_args_list:
            actual_types.add(
                call.kwargs.get("event_type", call.args[1] if len(call.args) > 1 else None)
            )

        # The _persist method passes keyword arguments.
        actual_kw_types = {c.kwargs["event_type"] for c in mock_repo.insert.call_args_list}
        assert actual_kw_types == expected_types

    async def test_wal_write_replay_cycle(self, tmp_path: Path) -> None:
        """Write entries to WAL, replay into mock repo, verify count."""
        wal_path = tmp_path / "audit.wal"
        wal = WriteAheadLog(wal_path)

        for i in range(5):
            wal.write({"entry": i, "event_type": "test", "run_id": str(uuid4())})

        mock_repo = AsyncMock()
        mock_repo.bulk_insert = AsyncMock(return_value=[uuid4() for _ in range(5)])

        replayed = await wal.replay(mock_repo)
        assert replayed == 5
        mock_repo.bulk_insert.assert_awaited_once()
        assert len(mock_repo.bulk_insert.call_args[0][0]) == 5

        # WAL file should be emptied after replay.
        assert wal_path.read_text(encoding="utf-8") == ""

    async def test_wal_corruption_recovery(self, tmp_path: Path) -> None:
        """WAL skips corrupt lines and replays valid ones."""
        wal_path = tmp_path / "corrupt.wal"

        valid_1 = json.dumps({"entry": 1, "event_type": "test"})
        corrupt = "this is not json {{{{"
        valid_2 = json.dumps({"entry": 2, "event_type": "test"})

        wal_path.write_text(f"{valid_1}\n{corrupt}\n{valid_2}\n", encoding="utf-8")

        wal = WriteAheadLog(wal_path)
        mock_repo = AsyncMock()
        mock_repo.bulk_insert = AsyncMock(return_value=[uuid4(), uuid4()])

        replayed = await wal.replay(mock_repo)
        assert replayed == 2
        inserted = mock_repo.bulk_insert.call_args[0][0]
        assert len(inserted) == 2

    async def test_audit_archiver_local_export(self, tmp_path: Path) -> None:
        """AuditArchiver exports partition to local filesystem."""
        archive_root = tmp_path / "archive"
        archiver = AuditArchiver(lite_mode=True, local_root=archive_root)

        export_dir = tmp_path / "export"
        result_path = archiver.export_partition(2026, 3, export_dir)

        expected = export_dir / "2026" / "03" / "audit_entries.jsonl"
        assert expected.exists()
        assert result_path == expected

        content = expected.read_text(encoding="utf-8")
        assert "2026-03" in content
