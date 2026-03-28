"""Domain models — Pydantic v2 data shapes used throughout the system."""

from regulatory_agent_kit.models.audit import (
    AuditEntry,
    AuditEventType,
    CheckpointDecision,
    CheckpointType,
    DecisionType,
)
from regulatory_agent_kit.models.changes import (
    ChangeSet,
    FileDiff,
    ReportBundle,
    TestFailure,
    TestResult,
)
from regulatory_agent_kit.models.events import RegulatoryEvent
from regulatory_agent_kit.models.impact_map import (
    ASTRegion,
    ConflictRecord,
    FileImpact,
    ImpactMap,
    RuleMatch,
)
from regulatory_agent_kit.models.pipeline import (
    TERMINAL_STATUSES,
    CostEstimate,
    PipelineConfig,
    PipelineInput,
    PipelineResult,
    PipelineStatus,
    PipelineStatusLiteral,
    RepoInput,
    RepoResult,
    RepoStatusLiteral,
)

# Resolve forward references now that all models are imported.
PipelineResult.model_rebuild()

__all__ = [
    "TERMINAL_STATUSES",
    # impact_map
    "ASTRegion",
    # audit
    "AuditEntry",
    "AuditEventType",
    # changes
    "ChangeSet",
    "CheckpointDecision",
    "CheckpointType",
    "ConflictRecord",
    # pipeline
    "CostEstimate",
    "DecisionType",
    "FileDiff",
    "FileImpact",
    "ImpactMap",
    "PipelineConfig",
    "PipelineInput",
    "PipelineResult",
    "PipelineStatus",
    "PipelineStatusLiteral",
    # events
    "RegulatoryEvent",
    "RepoInput",
    "RepoResult",
    "RepoStatusLiteral",
    "ReportBundle",
    "RuleMatch",
    "TestFailure",
    "TestResult",
]
