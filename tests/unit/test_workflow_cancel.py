"""Tests for the CompliancePipeline cancel signal handler."""

from __future__ import annotations

from regulatory_agent_kit.orchestration.workflows import CompliancePipeline


class TestCancelSignal:
    """Tests for the cancel_pipeline signal on CompliancePipeline."""

    def test_cancel_requested_defaults_false(self) -> None:
        pipeline = CompliancePipeline()
        assert pipeline._cancel_requested is False

    def test_cancel_requested_can_be_set(self) -> None:
        """Setting _cancel_requested to True should work as the signal handler does."""
        pipeline = CompliancePipeline()
        pipeline._cancel_requested = True
        assert pipeline._cancel_requested is True

    def test_build_cancelled_result_structure(self) -> None:
        pipeline = CompliancePipeline()
        pipeline._run_id = "test-run-123"
        result = pipeline._build_cancelled_result()

        assert result["run_id"] == "test-run-123"
        assert result["status"] == "cancelled"
        assert result["phase"] == "CANCELLED"
        assert pipeline._status == "cancelled"
        assert pipeline._phase == "CANCELLED"

    def test_build_rejected_result_still_works(self) -> None:
        """Ensure _build_rejected_result is not broken by cancel changes."""
        pipeline = CompliancePipeline()
        pipeline._run_id = "test-run-456"
        result = pipeline._build_rejected_result("impact_review")

        assert result["run_id"] == "test-run-456"
        assert result["status"] == "rejected"
        assert result["phase"] == "impact_review"

    def test_init_has_all_expected_fields(self) -> None:
        pipeline = CompliancePipeline()
        assert pipeline._run_id == ""
        assert pipeline._phase == "PENDING"
        assert pipeline._status == "pending"
        assert pipeline._impact_approved is False
        assert pipeline._merge_approved is False
        assert pipeline._impact_rejected is False
        assert pipeline._merge_rejected is False
        assert pipeline._cancel_requested is False
        assert pipeline._repo_results == []
        assert pipeline._cost_estimate == {}
