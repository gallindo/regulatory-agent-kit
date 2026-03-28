"""Event sources — pluggable triggers for compliance pipelines."""

from regulatory_agent_kit.event_sources.base import EventSource
from regulatory_agent_kit.event_sources.file import FileEventSource
from regulatory_agent_kit.event_sources.kafka import KafkaEventSource
from regulatory_agent_kit.event_sources.sqs import SQSEventSource
from regulatory_agent_kit.event_sources.starter import WorkflowStarter
from regulatory_agent_kit.event_sources.webhook import WebhookEventSource

__all__ = [
    "EventSource",
    "FileEventSource",
    "KafkaEventSource",
    "SQSEventSource",
    "WebhookEventSource",
    "WorkflowStarter",
]
