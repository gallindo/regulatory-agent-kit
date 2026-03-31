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
        except httpx.HTTPError:
            logger.warning("Failed to post to %s", self.webhook_url, exc_info=True)

    def _format_checkpoint_message(
        self,
        run_id: str,
        checkpoint_name: str,
        summary: str,
        approve_url: str | None = None,
    ) -> dict[str, Any]:
        """Build the Slack webhook payload for a checkpoint request."""
        text = (
            f":warning: *Checkpoint Required*\n"
            f"*Run:* `{run_id}`\n"
            f"*Checkpoint:* {checkpoint_name}\n"
            f"*Summary:* {summary}"
        )
        if approve_url:
            text += f"\n<{approve_url}|Approve/Reject>"
        return {"text": text, "channel": self.channel}

    def _format_pipeline_complete_message(
        self,
        run_id: str,
        summary: str,
    ) -> dict[str, Any]:
        """Build the Slack webhook payload for a pipeline-complete event."""
        return {
            "text": (f":white_check_mark: Pipeline `{run_id}` completed.\n{summary}"),
            "channel": self.channel,
        }

    def _format_error_message(
        self,
        run_id: str,
        error: str,
    ) -> dict[str, Any]:
        """Build the Slack webhook payload for an error event."""
        return {
            "text": f":x: Pipeline `{run_id}` failed.\n```{error}```",
            "channel": self.channel,
        }

    async def send_checkpoint_request(
        self,
        *,
        run_id: str,
        checkpoint_name: str,
        summary: str,
        approve_url: str | None = None,
    ) -> None:
        """Send checkpoint request via Slack webhook."""
        payload = self._format_checkpoint_message(run_id, checkpoint_name, summary, approve_url)
        await self._post(payload)

    async def send_pipeline_complete(
        self,
        *,
        run_id: str,
        summary: str,
    ) -> None:
        """Send pipeline-complete notification via Slack webhook."""
        payload = self._format_pipeline_complete_message(run_id, summary)
        await self._post(payload)

    async def send_error(
        self,
        *,
        run_id: str,
        error: str,
    ) -> None:
        """Send error notification via Slack webhook."""
        payload = self._format_error_message(run_id, error)
        await self._post(payload)


# ---------------------------------------------------------------------------
# Email implementation (SMTP)
# ---------------------------------------------------------------------------


@dataclass
class EmailNotifier:
    """Send notifications via email using SMTP."""

    smtp_host: str = "localhost"
    smtp_port: int = 587
    from_address: str = ""
    to_addresses: list[str] = field(default_factory=list)
    username: str = ""
    password: str = ""
    use_tls: bool = True

    async def _send_email(self, subject: str, body_html: str) -> None:
        """Send an HTML email via SMTP.

        Uses ``asyncio.to_thread`` to run the synchronous ``smtplib``
        operations without blocking the event loop.
        """
        import asyncio
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_address
        msg["To"] = ", ".join(self.to_addresses)
        msg.attach(MIMEText(body_html, "html"))

        def _send_sync() -> None:
            import smtplib

            server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30)
            try:
                if self.use_tls:
                    server.starttls()
                if self.username:
                    server.login(self.username, self.password)
                server.sendmail(
                    self.from_address, self.to_addresses, msg.as_string()
                )
            finally:
                server.quit()

        await asyncio.to_thread(_send_sync)
        logger.info("Email sent: subject=%s, to=%s", subject, self.to_addresses)

    def _checkpoint_html(
        self,
        run_id: str,
        checkpoint_name: str,
        summary: str,
        approve_url: str | None,
    ) -> str:
        """Format checkpoint request as HTML."""
        approve_link = ""
        if approve_url:
            approve_link = f'<p><a href="{approve_url}">Review and Approve</a></p>'
        return (
            f"<h2>Checkpoint Approval Required</h2>"
            f"<p><strong>Run ID:</strong> {run_id}</p>"
            f"<p><strong>Checkpoint:</strong> {checkpoint_name}</p>"
            f"<p><strong>Summary:</strong></p><p>{summary}</p>"
            f"{approve_link}"
        )

    def _complete_html(self, run_id: str, summary: str) -> str:
        """Format pipeline completion as HTML."""
        return (
            f"<h2>Pipeline Completed</h2>"
            f"<p><strong>Run ID:</strong> {run_id}</p>"
            f"<p><strong>Summary:</strong></p><p>{summary}</p>"
        )

    def _error_html(self, run_id: str, error: str) -> str:
        """Format error notification as HTML."""
        return (
            f"<h2>Pipeline Error</h2>"
            f"<p><strong>Run ID:</strong> {run_id}</p>"
            f"<p><strong>Error:</strong></p><pre>{error}</pre>"
        )

    async def send_checkpoint_request(
        self,
        *,
        run_id: str,
        checkpoint_name: str,
        summary: str,
        approve_url: str | None = None,
    ) -> None:
        """Send checkpoint approval request email."""
        subject = f"[RAK] Checkpoint approval required: {checkpoint_name} ({run_id[:8]})"
        body = self._checkpoint_html(run_id, checkpoint_name, summary, approve_url)
        await self._send_email(subject, body)

    async def send_pipeline_complete(
        self,
        *,
        run_id: str,
        summary: str,
    ) -> None:
        """Send pipeline completion notification email."""
        subject = f"[RAK] Pipeline completed ({run_id[:8]})"
        body = self._complete_html(run_id, summary)
        await self._send_email(subject, body)

    async def send_error(
        self,
        *,
        run_id: str,
        error: str,
    ) -> None:
        """Send pipeline error notification email."""
        subject = f"[RAK] Pipeline error ({run_id[:8]})"
        body = self._error_html(run_id, error)
        await self._send_email(subject, body)


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
        except httpx.HTTPError:
            logger.warning("Failed to post to %s", self.url, exc_info=True)

    def _format_checkpoint_payload(
        self,
        run_id: str,
        checkpoint_name: str,
        summary: str,
        approve_url: str | None = None,
    ) -> dict[str, Any]:
        """Build the webhook JSON payload for a checkpoint request."""
        return {
            "type": "checkpoint_request",
            "run_id": run_id,
            "checkpoint_name": checkpoint_name,
            "summary": summary,
            "approve_url": approve_url,
        }

    def _format_pipeline_complete_payload(
        self,
        run_id: str,
        summary: str,
    ) -> dict[str, Any]:
        """Build the webhook JSON payload for a pipeline-complete event."""
        return {
            "type": "pipeline_complete",
            "run_id": run_id,
            "summary": summary,
        }

    def _format_error_payload(
        self,
        run_id: str,
        error: str,
    ) -> dict[str, Any]:
        """Build the webhook JSON payload for an error event."""
        return {
            "type": "pipeline_error",
            "run_id": run_id,
            "error": error,
        }

    async def send_checkpoint_request(
        self,
        *,
        run_id: str,
        checkpoint_name: str,
        summary: str,
        approve_url: str | None = None,
    ) -> None:
        """Send checkpoint request via webhook."""
        payload = self._format_checkpoint_payload(run_id, checkpoint_name, summary, approve_url)
        await self._post(payload)

    async def send_pipeline_complete(
        self,
        *,
        run_id: str,
        summary: str,
    ) -> None:
        """Send pipeline-complete notification via webhook."""
        payload = self._format_pipeline_complete_payload(run_id, summary)
        await self._post(payload)

    async def send_error(
        self,
        *,
        run_id: str,
        error: str,
    ) -> None:
        """Send error notification via webhook."""
        payload = self._format_error_payload(run_id, error)
        await self._post(payload)


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
        "username": "",
        "password": "",
        "use_tls": True,
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
