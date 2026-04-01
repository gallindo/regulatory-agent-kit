"""Observability layer — audit logging, WAL, archival, evaluation, and setup."""

from __future__ import annotations

from regulatory_agent_kit.observability.audit_logger import AuditLogger
from regulatory_agent_kit.observability.evaluation import (
    AgentEvaluator,
    EvaluationResult,
    ScorerConfig,
)
from regulatory_agent_kit.observability.metrics import (
    MetricsRegistry,
    get_metrics_registry,
    instrumented_tool,
    record_checkpoint_decision,
    record_llm_call,
    record_pipeline_completed,
    record_pipeline_failed,
    record_pipeline_started,
    record_repo_processed,
    record_tool_invocation,
)
from regulatory_agent_kit.observability.setup import (
    AuditSignerLoader,
    MlflowSetup,
    ObservabilitySetup,
    OtelSetup,
)
from regulatory_agent_kit.observability.storage import (
    AuditArchiver,
    AzureBlobStorageBackend,
    GCSStorageBackend,
    LocalStorageBackend,
    S3StorageBackend,
    StorageBackend,
    create_storage_backend,
)
from regulatory_agent_kit.observability.wal import WriteAheadLog

__all__ = [
    "AgentEvaluator",
    "AuditArchiver",
    "AuditLogger",
    "AuditSignerLoader",
    "AzureBlobStorageBackend",
    "EvaluationResult",
    "GCSStorageBackend",
    "LocalStorageBackend",
    "MetricsRegistry",
    "MlflowSetup",
    "ObservabilitySetup",
    "OtelSetup",
    "S3StorageBackend",
    "ScorerConfig",
    "StorageBackend",
    "WriteAheadLog",
    "create_storage_backend",
    "get_metrics_registry",
    "instrumented_tool",
    "record_checkpoint_decision",
    "record_llm_call",
    "record_pipeline_completed",
    "record_pipeline_failed",
    "record_pipeline_started",
    "record_repo_processed",
    "record_tool_invocation",
]
