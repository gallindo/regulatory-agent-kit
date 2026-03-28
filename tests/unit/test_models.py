"""Unit tests for all domain models (Phase 1)."""

from datetime import datetime
from typing import ClassVar
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from regulatory_agent_kit.models import (
    TERMINAL_STATUSES,
    ASTRegion,
    AuditEntry,
    ChangeSet,
    CheckpointDecision,
    ConflictRecord,
    CostEstimate,
    FileDiff,
    FileImpact,
    ImpactMap,
    PipelineConfig,
    PipelineInput,
    PipelineResult,
    PipelineStatus,
    RegulatoryEvent,
    RepoInput,
    RepoResult,
    ReportBundle,
    RuleMatch,
    TestFailure,
    TestResult,
)

# ======================================================================
# RegulatoryEvent
# ======================================================================


class TestRegulatoryEvent:
    def test_valid_event(self) -> None:
        event = RegulatoryEvent(
            regulation_id="dora-ict-risk-2025",
            change_type="new_requirement",
            source="webhook",
        )
        assert isinstance(event.event_id, UUID)
        assert isinstance(event.timestamp, datetime)
        assert event.regulation_id == "dora-ict-risk-2025"
        assert event.change_type == "new_requirement"
        assert event.source == "webhook"
        assert event.payload == {}

    def test_valid_change_types(self) -> None:
        for ct in ("new_requirement", "amendment", "withdrawal"):
            event = RegulatoryEvent(regulation_id="test", change_type=ct, source="test")
            assert event.change_type == ct

    def test_invalid_change_type(self) -> None:
        with pytest.raises(ValidationError, match="change_type"):
            RegulatoryEvent(regulation_id="test", change_type="invalid", source="test")

    def test_empty_regulation_id_rejected(self) -> None:
        with pytest.raises(ValidationError, match="regulation_id"):
            RegulatoryEvent(regulation_id="", change_type="amendment", source="test")

    def test_missing_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            RegulatoryEvent()  # type: ignore[call-arg]

    def test_payload_with_data(self) -> None:
        event = RegulatoryEvent(
            regulation_id="test",
            change_type="amendment",
            source="kafka",
            payload={"article": "5.1", "details": "Updated requirement"},
        )
        assert event.payload["article"] == "5.1"

    def test_round_trip_dict(self) -> None:
        event = RegulatoryEvent(regulation_id="test", change_type="withdrawal", source="file")
        dumped = event.model_dump()
        restored = RegulatoryEvent.model_validate(dumped)
        assert restored == event

    def test_round_trip_json(self) -> None:
        event = RegulatoryEvent(regulation_id="test", change_type="new_requirement", source="sqs")
        json_str = event.model_dump_json()
        restored = RegulatoryEvent.model_validate_json(json_str)
        assert restored == event


# ======================================================================
# PipelineConfig
# ======================================================================


class TestPipelineConfig:
    def test_defaults(self) -> None:
        config = PipelineConfig()
        assert config.cost_threshold == 50.0
        assert config.auto_approve_cost is False
        assert config.checkpoint_mode == "terminal"
        assert config.max_retries == 2

    def test_negative_cost_rejected(self) -> None:
        with pytest.raises(ValidationError, match="cost_threshold"):
            PipelineConfig(cost_threshold=-1.0)

    def test_negative_retries_rejected(self) -> None:
        with pytest.raises(ValidationError, match="max_retries"):
            PipelineConfig(max_retries=-1)


# ======================================================================
# CostEstimate
# ======================================================================


class TestCostEstimate:
    def test_valid_estimate(self) -> None:
        est = CostEstimate(
            estimated_total_cost=12.50,
            estimated_total_tokens=50000,
            model_used="claude-sonnet-4-20250514",
            exceeds_threshold=False,
            per_repo_cost={"repo-a": 6.25, "repo-b": 6.25},
        )
        assert est.estimated_total_cost == 12.50
        assert est.exceeds_threshold is False

    def test_negative_cost_rejected(self) -> None:
        with pytest.raises(ValidationError):
            CostEstimate(
                estimated_total_cost=-1.0,
                estimated_total_tokens=0,
                model_used="test",
                exceeds_threshold=False,
            )


# ======================================================================
# PipelineInput / RepoInput
# ======================================================================


class TestPipelineInput:
    def test_valid_input(self) -> None:
        inp = PipelineInput(
            regulation_id="dora-ict-risk-2025",
            repo_urls=["https://github.com/org/repo-a"],
            plugin={"id": "dora-ict-risk-2025"},
        )
        assert inp.regulation_id == "dora-ict-risk-2025"
        assert len(inp.repo_urls) == 1

    def test_empty_repo_urls_rejected(self) -> None:
        with pytest.raises(ValidationError, match="repo_urls"):
            PipelineInput(
                regulation_id="test",
                repo_urls=[],
                plugin={"id": "test"},
            )


class TestRepoInput:
    def test_valid_repo_input(self) -> None:
        ri = RepoInput(
            repo_url="https://github.com/org/repo",
            plugin={"id": "test"},
            phase="analyze",
        )
        assert ri.phase == "analyze"
        assert ri.impact_map is None

    def test_invalid_phase(self) -> None:
        with pytest.raises(ValidationError, match="phase"):
            RepoInput(
                repo_url="https://github.com/org/repo",
                plugin={"id": "test"},
                phase="invalid",
            )


# ======================================================================
# RepoResult / PipelineResult
# ======================================================================


class TestRepoResult:
    def test_valid_result(self) -> None:
        result = RepoResult(
            repo_url="https://github.com/org/repo",
            status="completed",
            branch_name="rak/dora/ICT-001",
            pr_url="https://github.com/org/repo/pull/42",
        )
        assert result.status == "completed"

    def test_failed_with_error(self) -> None:
        result = RepoResult(
            repo_url="https://github.com/org/repo",
            status="failed",
            error="Clone failed: authentication error",
        )
        assert result.error is not None

    def test_invalid_status(self) -> None:
        with pytest.raises(ValidationError, match="status"):
            RepoResult(repo_url="https://github.com/org/repo", status="running")


class TestPipelineResult:
    def test_completed_with_report(self) -> None:
        report = ReportBundle(
            pr_urls=["https://github.com/org/repo/pull/1"],
            audit_log_path="/tmp/audit.json",  # noqa: S108
            report_path="/tmp/report.html",  # noqa: S108
            rollback_manifest_path="/tmp/rollback.json",  # noqa: S108
        )
        result = PipelineResult(status="completed", report=report)
        assert result.status == "completed"
        assert result.report is not None

    def test_completed_without_report_rejected(self) -> None:
        with pytest.raises(ValidationError, match="report"):
            PipelineResult(status="completed", report=None)

    def test_failed_without_report_ok(self) -> None:
        result = PipelineResult(status="failed")
        assert result.status == "failed"
        assert result.report is None

    def test_rejected_without_report_ok(self) -> None:
        result = PipelineResult(status="rejected")
        assert result.status == "rejected"

    def test_cost_rejected_ok(self) -> None:
        result = PipelineResult(status="cost_rejected")
        assert result.status == "cost_rejected"

    def test_invalid_status(self) -> None:
        with pytest.raises(ValidationError, match="status"):
            PipelineResult(status="pending")

    def test_round_trip(self) -> None:
        report = ReportBundle(
            pr_urls=[],
            audit_log_path="/audit.json",
            report_path="/report.html",
            rollback_manifest_path="/rollback.json",
        )
        result = PipelineResult(status="completed", report=report, actual_cost=5.25)
        dumped = result.model_dump()
        restored = PipelineResult.model_validate(dumped)
        assert restored == result


# ======================================================================
# PipelineStatus
# ======================================================================


class TestPipelineStatus:
    def test_valid_status(self) -> None:
        run_id = uuid4()
        ps = PipelineStatus(
            run_id=run_id,
            status="running",
            phase="ANALYZING",
            repo_counts={"pending": 2, "in_progress": 1},
            cost_summary={"estimated": 10.0, "actual": 3.0},
        )
        assert ps.run_id == run_id
        assert ps.status == "running"

    def test_all_valid_statuses(self) -> None:
        for status in (
            "pending",
            "running",
            "cost_rejected",
            "completed",
            "failed",
            "rejected",
            "cancelled",
        ):
            ps = PipelineStatus(run_id=uuid4(), status=status)
            assert ps.status == status

    def test_invalid_status(self) -> None:
        with pytest.raises(ValidationError):
            PipelineStatus(run_id=uuid4(), status="unknown")


# ======================================================================
# TERMINAL_STATUSES
# ======================================================================


class TestTerminalStatuses:
    def test_contains_expected(self) -> None:
        assert "completed" in TERMINAL_STATUSES
        assert "failed" in TERMINAL_STATUSES
        assert "rejected" in TERMINAL_STATUSES
        assert "cost_rejected" in TERMINAL_STATUSES
        assert "cancelled" in TERMINAL_STATUSES

    def test_excludes_non_terminal(self) -> None:
        assert "pending" not in TERMINAL_STATUSES
        assert "running" not in TERMINAL_STATUSES


# ======================================================================
# ASTRegion / RuleMatch / FileImpact / ConflictRecord / ImpactMap
# ======================================================================


class TestASTRegion:
    def test_valid_region(self) -> None:
        region = ASTRegion(
            start_line=10, end_line=20, start_col=0, end_col=50, node_type="class_declaration"
        )
        assert region.start_line == 10

    def test_zero_line_rejected(self) -> None:
        with pytest.raises(ValidationError, match="start_line"):
            ASTRegion(start_line=0, end_line=5, start_col=0, end_col=10, node_type="method")

    def test_round_trip(self) -> None:
        region = ASTRegion(start_line=1, end_line=5, start_col=0, end_col=80, node_type="function")
        assert ASTRegion.model_validate(region.model_dump()) == region


class TestRuleMatch:
    def test_valid_match(self) -> None:
        match = RuleMatch(
            rule_id="DORA-ICT-001",
            description="Structured logging required",
            severity="critical",
            confidence=0.92,
            condition_evaluated="has_annotation(@AuditLog)",
        )
        assert match.severity == "critical"

    def test_invalid_severity(self) -> None:
        with pytest.raises(ValidationError, match="severity"):
            RuleMatch(
                rule_id="X",
                description="test",
                severity="urgent",
                confidence=0.5,
                condition_evaluated="test",
            )

    def test_confidence_out_of_range(self) -> None:
        with pytest.raises(ValidationError, match="confidence"):
            RuleMatch(
                rule_id="X",
                description="test",
                severity="low",
                confidence=1.5,
                condition_evaluated="test",
            )


class TestFileImpact:
    def test_defaults(self) -> None:
        fi = FileImpact(file_path="src/main.py")
        assert fi.matched_rules == []
        assert fi.affected_regions == []

    def test_with_matches(self) -> None:
        fi = FileImpact(
            file_path="src/Service.java",
            matched_rules=[
                RuleMatch(
                    rule_id="R1",
                    description="test",
                    severity="high",
                    confidence=0.8,
                    condition_evaluated="cond",
                )
            ],
        )
        assert len(fi.matched_rules) == 1


class TestConflictRecord:
    def test_valid_conflict(self) -> None:
        region = ASTRegion(start_line=1, end_line=10, start_col=0, end_col=80, node_type="class")
        conflict = ConflictRecord(
            conflicting_rule_ids=["DORA-001", "GDPR-005"],
            affected_regions=[region],
            description="Overlapping logging requirements",
        )
        assert len(conflict.conflicting_rule_ids) == 2

    def test_single_rule_rejected(self) -> None:
        region = ASTRegion(start_line=1, end_line=1, start_col=0, end_col=1, node_type="x")
        with pytest.raises(ValidationError, match="conflicting_rule_ids"):
            ConflictRecord(
                conflicting_rule_ids=["only-one"],
                affected_regions=[region],
                description="test",
            )


class TestImpactMap:
    def test_valid_map(self) -> None:
        im = ImpactMap(analysis_confidence=0.85)
        assert im.files == []
        assert im.conflicts == []

    def test_confidence_range(self) -> None:
        with pytest.raises(ValidationError, match="analysis_confidence"):
            ImpactMap(analysis_confidence=1.5)

    def test_round_trip_json(self) -> None:
        im = ImpactMap(
            files=[FileImpact(file_path="a.py")],
            analysis_confidence=0.9,
        )
        json_str = im.model_dump_json()
        restored = ImpactMap.model_validate_json(json_str)
        assert restored == im


# ======================================================================
# ChangeSet / FileDiff / TestResult / TestFailure / ReportBundle
# ======================================================================


class TestFileDiff:
    def test_valid_diff(self) -> None:
        diff = FileDiff(
            file_path="src/main.py",
            rule_id="R1",
            diff_content="@@ -1 +1 @@\n-old\n+new",
            confidence=0.9,
            strategy_used="add_annotation",
        )
        assert diff.strategy_used == "add_annotation"


class TestChangeSet:
    def test_valid_changeset(self) -> None:
        cs = ChangeSet(
            branch_name="rak/dora/ICT-001",
            diffs=[
                FileDiff(
                    file_path="a.py",
                    rule_id="R1",
                    diff_content="diff",
                    confidence=0.8,
                    strategy_used="replace_pattern",
                )
            ],
            confidence_scores=[0.8],
            commit_sha="abc123",
        )
        assert len(cs.diffs) == 1


class TestTestFailure:
    def test_valid_failure(self) -> None:
        tf = TestFailure(
            test_name="test_audit_log",
            file_path="tests/test_audit.py",
            error_message="AssertionError: expected True",
        )
        assert tf.test_name == "test_audit_log"


class TestTestResult:
    def test_all_passing(self) -> None:
        tr = TestResult(pass_rate=1.0, total_tests=10, passed=10, failed=0)
        assert tr.failures == []

    def test_with_failures(self) -> None:
        tr = TestResult(
            pass_rate=0.5,
            total_tests=2,
            passed=1,
            failed=1,
            failures=[
                TestFailure(
                    test_name="test_x",
                    file_path="test.py",
                    error_message="fail",
                )
            ],
        )
        assert len(tr.failures) == 1

    def test_pass_rate_out_of_range(self) -> None:
        with pytest.raises(ValidationError, match="pass_rate"):
            TestResult(pass_rate=2.0, total_tests=1, passed=1, failed=0)


class TestReportBundle:
    def test_valid_bundle(self) -> None:
        rb = ReportBundle(
            pr_urls=["https://github.com/org/repo/pull/1"],
            audit_log_path="/tmp/audit.json",  # noqa: S108
            report_path="/tmp/report.html",  # noqa: S108
            rollback_manifest_path="/tmp/rollback.json",  # noqa: S108
        )
        assert len(rb.pr_urls) == 1

    def test_round_trip(self) -> None:
        rb = ReportBundle(
            audit_log_path="/a.json",
            report_path="/r.html",
            rollback_manifest_path="/rb.json",
        )
        assert ReportBundle.model_validate(rb.model_dump()) == rb


# ======================================================================
# AuditEntry
# ======================================================================


class TestAuditEntry:
    VALID_EVENT_TYPES: ClassVar[list[str]] = [
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

    def test_valid_entry(self) -> None:
        entry = AuditEntry(
            run_id=uuid4(),
            event_type="llm_call",
            payload={"model": "claude", "tokens": 100},
        )
        assert isinstance(entry.entry_id, UUID)
        assert entry.event_type == "llm_call"

    @pytest.mark.parametrize("event_type", VALID_EVENT_TYPES)
    def test_all_valid_event_types(self, event_type: str) -> None:
        entry = AuditEntry(run_id=uuid4(), event_type=event_type)
        assert entry.event_type == event_type

    def test_invalid_event_type(self) -> None:
        with pytest.raises(ValidationError, match="event_type"):
            AuditEntry(run_id=uuid4(), event_type="invalid_type")

    def test_exactly_9_valid_types(self) -> None:
        assert len(self.VALID_EVENT_TYPES) == 9

    def test_round_trip_dict(self) -> None:
        entry = AuditEntry(
            run_id=uuid4(),
            event_type="state_transition",
            payload={"from": "pending", "to": "running"},
            signature="sig123",
        )
        restored = AuditEntry.model_validate(entry.model_dump())
        assert restored == entry

    def test_round_trip_json(self) -> None:
        entry = AuditEntry(
            run_id=uuid4(),
            event_type="error",
            payload={"message": "Something failed"},
        )
        json_str = entry.model_dump_json()
        restored = AuditEntry.model_validate_json(json_str)
        assert restored == entry


# ======================================================================
# CheckpointDecision
# ======================================================================


class TestCheckpointDecision:
    def test_valid_decision(self) -> None:
        decision = CheckpointDecision(
            checkpoint_type="impact_review",
            actor="user@example.com",
            decision="approved",
            rationale="Looks good.",
        )
        assert decision.checkpoint_type == "impact_review"
        assert decision.decision == "approved"

    def test_valid_checkpoint_types(self) -> None:
        for ct in ("impact_review", "merge_review"):
            d = CheckpointDecision(
                checkpoint_type=ct, actor="user@example.com", decision="approved"
            )
            assert d.checkpoint_type == ct

    def test_invalid_checkpoint_type(self) -> None:
        with pytest.raises(ValidationError, match="checkpoint_type"):
            CheckpointDecision(
                checkpoint_type="invalid",
                actor="user@example.com",
                decision="approved",
            )

    def test_valid_decisions(self) -> None:
        for dec in ("approved", "rejected", "modifications_requested"):
            d = CheckpointDecision(checkpoint_type="merge_review", actor="admin", decision=dec)
            assert d.decision == dec

    def test_invalid_decision(self) -> None:
        with pytest.raises(ValidationError, match="decision"):
            CheckpointDecision(
                checkpoint_type="impact_review",
                actor="user@example.com",
                decision="maybe",
            )

    def test_empty_actor_rejected(self) -> None:
        with pytest.raises(ValidationError, match="actor"):
            CheckpointDecision(
                checkpoint_type="impact_review",
                actor="",
                decision="approved",
            )

    def test_round_trip(self) -> None:
        d = CheckpointDecision(
            checkpoint_type="merge_review",
            actor="admin@corp.com",
            decision="modifications_requested",
            rationale="Please add tests for edge cases.",
            signature="base64sig",
        )
        restored = CheckpointDecision.model_validate(d.model_dump())
        assert restored == d

    def test_round_trip_json(self) -> None:
        d = CheckpointDecision(
            checkpoint_type="impact_review",
            actor="dev@corp.com",
            decision="rejected",
        )
        json_str = d.model_dump_json()
        restored = CheckpointDecision.model_validate_json(json_str)
        assert restored == d


# ======================================================================
# Models __init__ exports
# ======================================================================


class TestModelExports:
    """Verify all public model classes are importable from regulatory_agent_kit.models."""

    EXPECTED_CLASSES: ClassVar[list[str]] = [
        "RegulatoryEvent",
        "PipelineConfig",
        "PipelineInput",
        "PipelineResult",
        "PipelineStatus",
        "RepoInput",
        "RepoResult",
        "CostEstimate",
        "ImpactMap",
        "FileImpact",
        "RuleMatch",
        "ASTRegion",
        "ConflictRecord",
        "ChangeSet",
        "FileDiff",
        "TestResult",
        "TestFailure",
        "ReportBundle",
        "AuditEntry",
        "CheckpointDecision",
    ]

    def test_all_classes_exported(self) -> None:
        import regulatory_agent_kit.models as models_mod

        for name in self.EXPECTED_CLASSES:
            assert hasattr(models_mod, name), f"{name} not exported from models"

    def test_at_least_15_model_classes(self) -> None:
        assert len(self.EXPECTED_CLASSES) >= 15
