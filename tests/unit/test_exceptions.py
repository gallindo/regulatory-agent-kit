"""Tests for the exception hierarchy (Phase 2)."""

from __future__ import annotations

import pytest

from regulatory_agent_kit.exceptions import (
    AgentError,
    ASTError,
    AuditSigningError,
    CheckpointRejectedError,
    CheckpointTimeoutError,
    ConditionParseError,
    CostThresholdExceededError,
    DatabaseError,
    EventSourceError,
    GitError,
    PipelineError,
    PluginLoadError,
    PluginValidationError,
    RAKError,
    TemplateError,
    ToolError,
)

ALL_EXCEPTION_CLASSES = [
    PluginValidationError,
    PluginLoadError,
    ConditionParseError,
    PipelineError,
    CheckpointTimeoutError,
    CheckpointRejectedError,
    CostThresholdExceededError,
    AgentError,
    ToolError,
    GitError,
    ASTError,
    TemplateError,
    AuditSigningError,
    EventSourceError,
    DatabaseError,
]


class TestExceptionHierarchy:
    @pytest.mark.parametrize("exc_class", ALL_EXCEPTION_CLASSES)
    def test_inherits_from_rak_error(self, exc_class: type[RAKError]) -> None:
        assert issubclass(exc_class, RAKError)

    @pytest.mark.parametrize("exc_class", ALL_EXCEPTION_CLASSES)
    def test_catchable_by_parent(self, exc_class: type[RAKError]) -> None:
        with pytest.raises(RAKError):
            raise exc_class("test error")

    @pytest.mark.parametrize("exc_class", ALL_EXCEPTION_CLASSES)
    def test_message_preserved(self, exc_class: type[RAKError]) -> None:
        err = exc_class("specific message")
        assert str(err) == "specific message"

    def test_total_exception_count(self) -> None:
        assert len(ALL_EXCEPTION_CLASSES) == 15

    def test_git_error_is_tool_error(self) -> None:
        assert issubclass(GitError, ToolError)
        with pytest.raises(ToolError):
            raise GitError("git clone failed")

    def test_ast_error_is_tool_error(self) -> None:
        assert issubclass(ASTError, ToolError)
        with pytest.raises(ToolError):
            raise ASTError("parse failed")
