"""Pipeline models — inputs, configuration, results, and status tracking."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

if TYPE_CHECKING:
    from regulatory_agent_kit.models.changes import ReportBundle

# ---------------------------------------------------------------------------
# Pipeline lifecycle statuses
# ---------------------------------------------------------------------------

PipelineStatusLiteral = Literal[
    "pending",
    "running",
    "cost_rejected",
    "completed",
    "failed",
    "rejected",
    "cancelled",
]

TERMINAL_STATUSES: frozenset[str] = frozenset(
    {"completed", "failed", "rejected", "cost_rejected", "cancelled"}
)

ALL_STATUSES: tuple[str, ...] = (
    "pending",
    "running",
    "cost_rejected",
    "completed",
    "failed",
    "rejected",
    "cancelled",
)

RepoStatusLiteral = Literal["pending", "in_progress", "completed", "failed", "skipped"]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class PipelineConfig(BaseModel):
    """Configuration for a single pipeline run."""

    default_model: str = Field(
        default="claude-sonnet-4-20250514",
        description="LLM model identifier for agent calls.",
    )
    cost_threshold: float = Field(
        default=50.0,
        ge=0,
        description="Maximum allowed LLM cost in USD before human approval.",
    )
    auto_approve_cost: bool = Field(
        default=False,
        description="Skip cost-approval checkpoint when estimate is below threshold.",
    )
    checkpoint_mode: str = Field(
        default="terminal",
        description="How human checkpoints are delivered: terminal, slack, email, webhook.",
    )
    max_retries: int = Field(
        default=2,
        ge=0,
        description="Maximum retries for failed activities.",
    )


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


class RepoInput(BaseModel):
    """Input for per-repository processing (child workflow)."""

    repo_url: str = Field(..., min_length=1, description="Repository URL to process.")
    plugin: Any = Field(..., description="RegulationPlugin instance.")
    phase: Literal["analyze", "refactor_and_test"] = Field(..., description="Processing phase.")
    impact_map: Any | None = Field(
        default=None, description="ImpactMap from analysis phase (if in refactor phase)."
    )


class PipelineInput(BaseModel):
    """Top-level input to the compliance pipeline workflow."""

    regulation_id: str = Field(
        ..., min_length=1, description="Plugin ID for the target regulation."
    )
    repo_urls: list[str] = Field(..., min_length=1, description="List of repository URLs to scan.")
    plugin: Any = Field(..., description="Loaded RegulationPlugin instance.")
    config: PipelineConfig = Field(
        default_factory=PipelineConfig, description="Pipeline configuration."
    )


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------


class CostEstimate(BaseModel):
    """Pre-run cost estimate produced by the cost estimation activity."""

    estimated_total_cost: float = Field(..., ge=0, description="Total estimated LLM cost in USD.")
    per_repo_cost: dict[str, float] = Field(
        default_factory=dict,
        description="Estimated cost per repository URL.",
    )
    estimated_total_tokens: int = Field(..., ge=0, description="Total estimated token usage.")
    model_used: str = Field(..., min_length=1, description="Model used for estimation.")
    exceeds_threshold: bool = Field(
        ..., description="Whether the estimate exceeds the configured cost threshold."
    )


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


class RepoResult(BaseModel):
    """Result of processing a single repository."""

    repo_url: str = Field(..., min_length=1, description="Repository URL.")
    status: Literal["completed", "failed", "skipped"] = Field(
        ..., description="Processing outcome."
    )
    branch_name: str | None = Field(default=None, description="Branch created for remediation.")
    pr_url: str | None = Field(default=None, description="Pull request URL.")
    error: str | None = Field(default=None, description="Error message if failed.")


class PipelineResult(BaseModel):
    """Final result of a compliance pipeline run."""

    run_id: UUID = Field(default_factory=uuid4, description="Pipeline run identifier.")
    status: Literal["completed", "rejected", "failed", "cost_rejected"] = Field(
        ..., description="Terminal pipeline status."
    )
    report: ReportBundle | None = Field(
        default=None, description="ReportBundle if pipeline completed successfully."
    )
    actual_cost: float = Field(default=0.0, ge=0, description="Actual LLM cost in USD.")

    @model_validator(mode="after")
    def _validate_terminal_status(self) -> PipelineResult:
        """Terminal statuses 'completed' and 'cost_rejected' have additional requirements."""
        if self.status == "completed" and self.report is None:
            msg = "Completed pipelines must include a report."
            raise ValueError(msg)
        return self


# ---------------------------------------------------------------------------
# Pipeline status (query response)
# ---------------------------------------------------------------------------


class PipelineStatus(BaseModel):
    """Real-time pipeline status returned by CompliancePipeline.query_status()."""

    run_id: UUID = Field(..., description="Pipeline run identifier.")
    status: PipelineStatusLiteral = Field(..., description="Current lifecycle status.")
    phase: str = Field(
        default="",
        description="Current Temporal workflow phase (e.g., 'ANALYZING').",
    )
    repo_counts: dict[str, int] = Field(
        default_factory=dict,
        description="Repository counts by status (pending, in_progress, completed, failed).",
    )
    cost_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Cost information: estimated, actual, threshold.",
    )
