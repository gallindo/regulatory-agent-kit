"""Change and test result models — outputs of the Refactor, TestGenerator, and Reporter agents."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FileDiff(BaseModel):
    """A diff for a single file produced by the Refactor agent."""

    file_path: str = Field(..., min_length=1, description="Path to the modified file.")
    rule_id: str = Field(..., min_length=1, description="Rule that triggered this change.")
    diff_content: str = Field(..., description="Unified diff content.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Agent confidence in the change.")
    strategy_used: str = Field(..., min_length=1, description="Remediation strategy applied.")


class ChangeSet(BaseModel):
    """Collection of file changes produced by the Refactor agent."""

    branch_name: str = Field(..., min_length=1, description="Git branch name for the changes.")
    diffs: list[FileDiff] = Field(default_factory=list, description="Per-file diffs.")
    confidence_scores: list[float] = Field(
        default_factory=list, description="Per-diff confidence scores."
    )
    commit_sha: str = Field(default="", description="Git commit SHA of the remediation commit.")


class TestFailure(BaseModel):
    """A single test failure from the TestGenerator agent."""

    test_name: str = Field(..., min_length=1, description="Fully qualified test name.")
    file_path: str = Field(..., min_length=1, description="Path to the test file.")
    error_message: str = Field(..., description="Error message from the test runner.")
    stack_trace: str = Field(default="", description="Stack trace if available.")


class TestResult(BaseModel):
    """Aggregated test execution results from the TestGenerator agent."""

    pass_rate: float = Field(..., ge=0.0, le=1.0, description="Fraction of tests that passed.")
    total_tests: int = Field(..., ge=0, description="Total number of tests run.")
    passed: int = Field(..., ge=0, description="Number of tests that passed.")
    failed: int = Field(..., ge=0, description="Number of tests that failed.")
    failures: list[TestFailure] = Field(
        default_factory=list, description="Details of failed tests."
    )
    test_files_created: list[str] = Field(
        default_factory=list, description="Paths to generated test files."
    )


class ReportBundle(BaseModel):
    """Final report bundle produced by the Reporter agent."""

    pr_urls: list[str] = Field(default_factory=list, description="Pull request URLs created.")
    audit_log_path: str = Field(..., min_length=1, description="Path to the audit log export.")
    report_path: str = Field(..., min_length=1, description="Path to the compliance report.")
    rollback_manifest_path: str = Field(
        ..., min_length=1, description="Path to the rollback manifest."
    )
