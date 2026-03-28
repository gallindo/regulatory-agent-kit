"""Custom exception types for regulatory-agent-kit."""


class RAKError(Exception):
    """Base exception for all regulatory-agent-kit errors."""


class PluginValidationError(RAKError):
    """Raised when a regulation plugin fails schema validation."""


class PipelineError(RAKError):
    """Raised when a pipeline execution encounters an unrecoverable error."""


class CheckpointTimeoutError(RAKError):
    """Raised when a human checkpoint approval times out."""
