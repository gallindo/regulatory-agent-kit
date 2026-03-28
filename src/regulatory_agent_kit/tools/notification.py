"""Notification clients for pipeline checkpoint delivery."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import httpx

from regulatory_agent_kit.exceptions import ToolError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class NotificationClient(Protocol):
    """Interface for delivering pipeline notifications to humans."""

    async def send_checkpoint_request(
        self,
        *,
        run_id: str,
        checkpoint_name: str,
        summary: str,
        approve_url: str | None = None,
    ) -> None:
        """Send a checkpoint-approval request."""
        ...  # pragma: no cover

    async def send_pipeline_complete(
        self,
        *,
        run_id: str,
        summary: str,
    ) -> None:
        """Notify that a pipeline has completed."""
        ...  # pragma: no cover

    async def send_error(
        self,
        *,
        run_id: str,
        error: str,
    ) -> None:
        """Notify that a pipeline encountered an error."""
        ...  # pragma: no cover


# ---------------------------------------------------------------------------
# Slack implementation
# ---------------------------------------------------------------------------


@dataclass
class SlackNotifier:
    """Send notifications to a Slack channel via an incoming-webhook URL."""

    webhook_url: str
    channel: str = ""

    async def _post(self, payload: dict[str, Any]) -> None:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(self.webhook_url, json=payload)
                resp.raise_for_status()
        except Exception:
            logger.warning("Failed to send Slack notification", exc_info=True)

    async def send_checkpoint_request(
        self,
        *,
        run_id: str,
        checkpoint_name: str,
        summary: str,
        approve_url: str | None = None,
    ) -> None:
        """Send checkpoint request via Slack webhook."""
        text = (
            f":warning: *Checkpoint Required*\n"
            f"*Run:* `{run_id}`\n"
            f"*Checkpoint:* {checkpoint_name}\n"
            f"*Summary:* {summary}"
        )
        if approve_url:
            text += f"\n<{approve_url}|Approve/Reject>"
        await self._post({"text": text, "channel": self.channel})

    async def send_pipeline_complete(
        self,
        *,
        run_id: str,
        summary: str,
    ) -> None:
        """Send pipeline-complete notification via Slack webhook."""
        await self._post(
            {
                "text": f":white_check_mark: Pipeline `{run_id}` completed.\n{summary}",
                "channel": self.channel,
            }
        )

    async def send_error(
        self,
        *,
        run_id: str,
        error: str,
    ) -> None:
        """Send error notification via Slack webhook."""
        await self._post(
            {
                "text": f":x: Pipeline `{run_id}` failed.\n```{error}```",
                "channel": self.channel,
            }
        )


# ---------------------------------------------------------------------------
# Email implementation (stub — would use SMTP/SES in production)
# ---------------------------------------------------------------------------


@dataclass
class EmailNotifier:
    """Send notifications via email (stub implementation)."""

    smtp_host: str = "localhost"
    smtp_port: int = 587
    from_address: str = ""
    to_addresses: list[str] = field(default_factory=list)

    async def send_checkpoint_request(
        self,
        *,
        run_id: str,
        checkpoint_name: str,
        summary: str,
        approve_url: str | None = None,
    ) -> None:
        """Send checkpoint request via email (stub)."""
        logger.info(
            "Email checkpoint request: run=%s checkpoint=%s",
            run_id,
            checkpoint_name,
        )

    async def send_pipeline_complete(
        self,
        *,
        run_id: str,
        summary: str,
    ) -> None:
        """Send pipeline-complete notification via email (stub)."""
        logger.info("Email pipeline complete: run=%s", run_id)

    async def send_error(
        self,
        *,
        run_id: str,
        error: str,
    ) -> None:
        """Send error notification via email (stub)."""
        logger.info("Email error: run=%s error=%s", run_id, error)


# ---------------------------------------------------------------------------
# Webhook implementation
# ---------------------------------------------------------------------------


@dataclass
class WebhookNotifier:
    """Send notifications to an arbitrary HTTP endpoint."""

    url: str
    headers: dict[str, str] = field(default_factory=dict)

    async def _post(self, payload: dict[str, Any]) -> None:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(self.url, json=payload, headers=self.headers)
                resp.raise_for_status()
        except Exception:
            logger.warning("Failed to send webhook notification", exc_info=True)

    async def send_checkpoint_request(
        self,
        *,
        run_id: str,
        checkpoint_name: str,
        summary: str,
        approve_url: str | None = None,
    ) -> None:
        """Send checkpoint request via webhook."""
        await self._post(
            {
                "type": "checkpoint_request",
                "run_id": run_id,
                "checkpoint_name": checkpoint_name,
                "summary": summary,
                "approve_url": approve_url,
            }
        )

    async def send_pipeline_complete(
        self,
        *,
        run_id: str,
        summary: str,
    ) -> None:
        """Send pipeline-complete notification via webhook."""
        await self._post(
            {
                "type": "pipeline_complete",
                "run_id": run_id,
                "summary": summary,
            }
        )

    async def send_error(
        self,
        *,
        run_id: str,
        error: str,
    ) -> None:
        """Send error notification via webhook."""
        await self._post(
            {
                "type": "pipeline_error",
                "run_id": run_id,
                "error": error,
            }
        )


# ---------------------------------------------------------------------------
# Registry + Factory
# ---------------------------------------------------------------------------

_NOTIFIER_REGISTRY: dict[str, type[NotificationClient]] = {}


def register_notifier(mode: str, cls: type[NotificationClient]) -> None:
    """Register a notifier class for a given checkpoint mode."""
    _NOTIFIER_REGISTRY[mode] = cls


# Built-in registrations
register_notifier("slack", SlackNotifier)
register_notifier("email", EmailNotifier)
register_notifier("webhook", WebhookNotifier)
register_notifier("terminal", WebhookNotifier)

# Mapping from mode to the kwargs extractor used by the factory.
_NOTIFIER_DEFAULTS: dict[str, dict[str, Any]] = {
    "slack": {"webhook_url": "", "channel": ""},
    "email": {
        "smtp_host": "localhost",
        "smtp_port": 587,
        "from_address": "",
        "to_addresses": [],
    },
    "webhook": {"url": "", "headers": {}},
    "terminal": {"url": "", "headers": {}},
}


def create_notifier(
    checkpoint_mode: str,
    config: dict[str, Any] | None = None,
) -> NotificationClient:
    """Return the appropriate notifier based on *checkpoint_mode*.

    Supported modes: ``slack``, ``email``, ``webhook``, ``terminal``.

    Raises:
        ToolError: When the mode is not supported.
    """
    cls = _NOTIFIER_REGISTRY.get(checkpoint_mode)
    if cls is None:
        msg = f"Unsupported checkpoint mode: {checkpoint_mode}"
        raise ToolError(msg)

    cfg = config or {}
    defaults = _NOTIFIER_DEFAULTS.get(checkpoint_mode, {})
    kwargs = {k: cfg.get(k, v) for k, v in defaults.items()}
    return cls(**kwargs)
