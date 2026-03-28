"""Tests for agent definitions — Phase 10."""

from __future__ import annotations

import re

from pydantic_ai.models.test import TestModel

from regulatory_agent_kit.agents import (
    ANALYZER_TOOLS,
    REFACTOR_TOOLS,
    REPORTER_TOOLS,
    TEST_GENERATOR_TOOLS,
    analyzer_agent,
    refactor_agent,
    reporter_agent,
    test_generator_agent,
)
from regulatory_agent_kit.agents.tools import (
    ast_parse,
    ast_search,
    ast_transform,
    es_search,
    git_branch,
    git_clone,
    git_commit,
    git_pr_create,
    git_read,
    jinja_render,
    jinja_render_report,
    jinja_render_test,
    notification_send,
    run_tests,
)
from regulatory_agent_kit.models import (
    ChangeSet,
    ImpactMap,
    ReportBundle,
    TestResult,
)

# ---------------------------------------------------------------------------
# Agent instantiation tests
# ---------------------------------------------------------------------------


class TestAnalyzerAgent:
    """Tests for the AnalyzerAgent."""

    def test_agent_exists(self) -> None:
        assert analyzer_agent is not None

    def test_agent_name(self) -> None:
        assert analyzer_agent.name == "rak-analyzer"

    def test_output_type(self) -> None:
        assert analyzer_agent.output_type == ImpactMap

    def test_system_prompt_is_regulation_agnostic(self) -> None:
        prompt = analyzer_agent._system_prompts[0]
        assert isinstance(prompt, str)
        # Should NOT contain hardcoded regulation IDs like DORA, GDPR, etc.
        regulation_ids = re.compile(r"\b(DORA|GDPR|SOX|PCI.?DSS|HIPAA|NIS2)\b", re.IGNORECASE)
        assert not regulation_ids.search(prompt), (
            "System prompt contains hardcoded regulation identifiers"
        )

    def test_has_only_readonly_tools(self) -> None:
        tool_names = _get_tool_names(analyzer_agent)
        # Must contain read-only tools
        assert "git_clone" in tool_names
        assert "ast_parse" in tool_names
        assert "ast_search" in tool_names
        assert "es_search" in tool_names
        # Must NOT contain write/external tools
        assert "git_commit" not in tool_names
        assert "git_branch" not in tool_names
        assert "git_pr_create" not in tool_names
        assert "run_tests" not in tool_names


class TestRefactorAgent:
    """Tests for the RefactorAgent."""

    def test_agent_exists(self) -> None:
        assert refactor_agent is not None

    def test_agent_name(self) -> None:
        assert refactor_agent.name == "rak-refactor"

    def test_output_type(self) -> None:
        assert refactor_agent.output_type == ChangeSet

    def test_system_prompt_is_regulation_agnostic(self) -> None:
        prompt = refactor_agent._system_prompts[0]
        assert isinstance(prompt, str)
        regulation_ids = re.compile(r"\b(DORA|GDPR|SOX|PCI.?DSS|HIPAA|NIS2)\b", re.IGNORECASE)
        assert not regulation_ids.search(prompt)

    def test_has_readwrite_tools(self) -> None:
        tool_names = _get_tool_names(refactor_agent)
        assert "git_branch" in tool_names
        assert "git_commit" in tool_names
        assert "ast_transform" in tool_names
        assert "jinja_render" in tool_names
        # Must NOT contain external/sandbox tools
        assert "git_pr_create" not in tool_names
        assert "run_tests" not in tool_names


class TestTestGeneratorAgent:
    """Tests for the TestGeneratorAgent."""

    def test_agent_exists(self) -> None:
        assert test_generator_agent is not None

    def test_agent_name(self) -> None:
        assert test_generator_agent.name == "rak-test-generator"

    def test_output_type(self) -> None:
        assert test_generator_agent.output_type == TestResult

    def test_system_prompt_is_regulation_agnostic(self) -> None:
        prompt = test_generator_agent._system_prompts[0]
        assert isinstance(prompt, str)
        regulation_ids = re.compile(r"\b(DORA|GDPR|SOX|PCI.?DSS|HIPAA|NIS2)\b", re.IGNORECASE)
        assert not regulation_ids.search(prompt)

    def test_has_sandboxed_tools(self) -> None:
        tool_names = _get_tool_names(test_generator_agent)
        assert "git_read" in tool_names
        assert "run_tests" in tool_names
        assert "jinja_render_test" in tool_names
        # Must NOT contain write/external tools
        assert "git_commit" not in tool_names
        assert "git_pr_create" not in tool_names
        assert "git_clone" not in tool_names


class TestReporterAgent:
    """Tests for the ReporterAgent."""

    def test_agent_exists(self) -> None:
        assert reporter_agent is not None

    def test_agent_name(self) -> None:
        assert reporter_agent.name == "rak-reporter"

    def test_output_type(self) -> None:
        assert reporter_agent.output_type == ReportBundle

    def test_system_prompt_is_regulation_agnostic(self) -> None:
        prompt = reporter_agent._system_prompts[0]
        assert isinstance(prompt, str)
        regulation_ids = re.compile(r"\b(DORA|GDPR|SOX|PCI.?DSS|HIPAA|NIS2)\b", re.IGNORECASE)
        assert not regulation_ids.search(prompt)

    def test_has_external_tools(self) -> None:
        tool_names = _get_tool_names(reporter_agent)
        assert "git_pr_create" in tool_names
        assert "notification_send" in tool_names
        assert "jinja_render_report" in tool_names
        # Must NOT contain analysis/sandbox tools
        assert "git_clone" not in tool_names
        assert "run_tests" not in tool_names
        assert "ast_parse" not in tool_names


# ---------------------------------------------------------------------------
# Tool isolation tests
# ---------------------------------------------------------------------------


class TestToolIsolation:
    """Verify that tool groups are disjoint across agents."""

    def test_analyzer_tools_are_readonly(self) -> None:
        assert git_clone in ANALYZER_TOOLS
        assert ast_parse in ANALYZER_TOOLS
        assert ast_search in ANALYZER_TOOLS
        assert es_search in ANALYZER_TOOLS
        assert len(ANALYZER_TOOLS) == 4

    def test_refactor_tools_are_readwrite(self) -> None:
        assert git_branch in REFACTOR_TOOLS
        assert git_commit in REFACTOR_TOOLS
        assert ast_transform in REFACTOR_TOOLS
        assert jinja_render in REFACTOR_TOOLS
        assert len(REFACTOR_TOOLS) == 4

    def test_test_generator_tools_are_sandboxed(self) -> None:
        assert git_read in TEST_GENERATOR_TOOLS
        assert run_tests in TEST_GENERATOR_TOOLS
        assert jinja_render_test in TEST_GENERATOR_TOOLS
        assert len(TEST_GENERATOR_TOOLS) == 3

    def test_reporter_tools_are_external(self) -> None:
        assert git_pr_create in REPORTER_TOOLS
        assert notification_send in REPORTER_TOOLS
        assert jinja_render_report in REPORTER_TOOLS
        assert len(REPORTER_TOOLS) == 3

    def test_no_overlap_between_tool_groups(self) -> None:
        groups = [
            set(id(t) for t in ANALYZER_TOOLS),
            set(id(t) for t in REFACTOR_TOOLS),
            set(id(t) for t in TEST_GENERATOR_TOOLS),
            set(id(t) for t in REPORTER_TOOLS),
        ]
        for i, group_a in enumerate(groups):
            for group_b in groups[i + 1 :]:
                assert group_a.isdisjoint(group_b), "Tool groups must not overlap"


# ---------------------------------------------------------------------------
# Agent with TestModel integration
# ---------------------------------------------------------------------------


class TestAgentWithTestModel:
    """Verify agents can be overridden with TestModel for testing."""

    def test_analyzer_override(self) -> None:
        with analyzer_agent.override(model=TestModel()):
            assert analyzer_agent.name == "rak-analyzer"

    def test_refactor_override(self) -> None:
        with refactor_agent.override(model=TestModel()):
            assert refactor_agent.name == "rak-refactor"

    def test_test_generator_override(self) -> None:
        with test_generator_agent.override(model=TestModel()):
            assert test_generator_agent.name == "rak-test-generator"

    def test_reporter_override(self) -> None:
        with reporter_agent.override(model=TestModel()):
            assert reporter_agent.name == "rak-reporter"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_tool_names(agent: object) -> set[str]:
    """Extract tool function names from an agent's registered tools."""
    toolset = getattr(agent, "_function_toolset", None)
    if toolset is None:
        return set()
    tools_dict: dict[str, object] = getattr(toolset, "tools", {})
    return set(tools_dict.keys())
