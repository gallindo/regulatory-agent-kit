"""Custom exception types for regulatory-agent-kit."""


class RAKError(Exception):
    """Base exception for all regulatory-agent-kit errors."""


# --- Plugin errors ---


class PluginValidationError(RAKError):
    """Raised when a regulation plugin fails schema validation."""


class PluginLoadError(RAKError):
    """Raised when a regulation plugin file cannot be loaded or parsed."""


class ConditionParseError(RAKError):
    """Raised when a Condition DSL expression is syntactically invalid."""


# --- Pipeline / orchestration errors ---


class PipelineError(RAKError):
    """Raised when a pipeline execution encounters an unrecoverable error."""


class CheckpointTimeoutError(RAKError):
    """Raised when a human checkpoint approval times out."""


class CheckpointRejectedError(RAKError):
    """Raised when a human checkpoint is explicitly rejected."""


class CostThresholdExceededError(RAKError):
    """Raised when the estimated LLM cost exceeds the configured threshold."""


# --- Agent / tool errors ---


class AgentError(RAKError):
    """Raised when a PydanticAI agent encounters an unrecoverable error."""


class ToolError(RAKError):
    """Raised when an agent tool fails during execution."""


class GitError(ToolError):
    """Raised when a git operation fails."""


class ASTError(ToolError):
    """Raised when AST parsing or querying fails."""


class TemplateError(RAKError):
    """Raised when Jinja2 template rendering or validation fails."""


# --- Infrastructure errors ---


class AuditSigningError(RAKError):
    """Raised when Ed25519 audit signing or verification fails."""


class EventSourceError(RAKError):
    """Raised when an event source encounters an error."""


class DatabaseError(RAKError):
    """Raised when a database operation fails."""
