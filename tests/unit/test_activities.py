"""Unit tests for Temporal activity definitions."""

from __future__ import annotations

from regulatory_agent_kit.orchestration.activities import (
    ALL_ACTIVITIES,
    analyze_repository,
    estimate_cost,
    refactor_repository,
    report_results,
)
from regulatory_agent_kit.orchestration.activities import (
    test_repository as _test_repository,
)


class TestActivityDecorators:
    """Verify each activity is properly decorated with @activity.defn."""

    def test_estimate_cost_is_activity(self) -> None:
        assert hasattr(estimate_cost, "__temporal_activity_definition")

    def test_analyze_repository_is_activity(self) -> None:
        assert hasattr(analyze_repository, "__temporal_activity_definition")

    def test_refactor_repository_is_activity(self) -> None:
        assert hasattr(refactor_repository, "__temporal_activity_definition")

    def test_test_repository_is_activity(self) -> None:
        assert hasattr(_test_repository, "__temporal_activity_definition")

    def test_report_results_is_activity(self) -> None:
        assert hasattr(report_results, "__temporal_activity_definition")


class TestActivityFunctions:
    """Verify each activity function exists and is callable."""

    def test_estimate_cost_callable(self) -> None:
        assert callable(estimate_cost)

    def test_analyze_repository_callable(self) -> None:
        assert callable(analyze_repository)

    def test_refactor_repository_callable(self) -> None:
        assert callable(refactor_repository)

    def test_test_repository_callable(self) -> None:
        assert callable(_test_repository)

    def test_report_results_callable(self) -> None:
        assert callable(report_results)

    def test_all_activities_list_contains_five(self) -> None:
        assert len(ALL_ACTIVITIES) == 5

    def test_all_activities_list_contents(self) -> None:
        expected = {
            estimate_cost,
            analyze_repository,
            refactor_repository,
            _test_repository,
            report_results,
        }
        assert set(ALL_ACTIVITIES) == expected
