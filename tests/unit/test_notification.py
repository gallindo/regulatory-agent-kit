"""Tests for notification clients (Phase 7)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from regulatory_agent_kit.exceptions import ToolError
from regulatory_agent_kit.tools.notification import (
    EmailNotifier,
    NotificationClient,
    SlackNotifier,
    WebhookNotifier,
    create_notifier,
)

# ======================================================================
# create_notifier factory
# ======================================================================


class TestCreateNotifier:
    """Test the notification factory function."""

    def test_slack_mode(self) -> None:
        notifier = create_notifier("slack", {"webhook_url": "https://hooks.slack.com/x"})
        assert isinstance(notifier, SlackNotifier)

    def test_email_mode(self) -> None:
        notifier = create_notifier("email")
        assert isinstance(notifier, EmailNotifier)

    def test_webhook_mode(self) -> None:
        notifier = create_notifier("webhook", {"url": "https://example.com/hook"})
        assert isinstance(notifier, WebhookNotifier)

    def test_terminal_mode(self) -> None:
        notifier = create_notifier("terminal")
        assert isinstance(notifier, WebhookNotifier)

    def test_unsupported_mode_raises(self) -> None:
        with pytest.raises(ToolError, match="Unsupported"):
            create_notifier("pigeon_carrier")


# ======================================================================
# Protocol conformance
# ======================================================================


class TestProtocolConformance:
    """Verify all notifiers satisfy the NotificationClient protocol."""

    def test_slack_is_notification_client(self) -> None:
        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/x")
        assert isinstance(notifier, NotificationClient)

    def test_email_is_notification_client(self) -> None:
        notifier = EmailNotifier()
        assert isinstance(notifier, NotificationClient)

    def test_webhook_is_notification_client(self) -> None:
        notifier = WebhookNotifier(url="https://example.com/hook")
        assert isinstance(notifier, NotificationClient)


# ======================================================================
# Methods are callable
# ======================================================================


class TestNotificationMethods:
    """Verify notification methods exist and are callable."""

    def test_slack_has_all_methods(self) -> None:
        n = SlackNotifier(webhook_url="")
        assert callable(n.send_checkpoint_request)
        assert callable(n.send_pipeline_complete)
        assert callable(n.send_error)

    def test_email_has_all_methods(self) -> None:
        n = EmailNotifier()
        assert callable(n.send_checkpoint_request)
        assert callable(n.send_pipeline_complete)
        assert callable(n.send_error)

    def test_webhook_has_all_methods(self) -> None:
        n = WebhookNotifier(url="")
        assert callable(n.send_checkpoint_request)
        assert callable(n.send_pipeline_complete)
        assert callable(n.send_error)

    async def test_email_send_checkpoint_does_not_raise(self) -> None:
        n = EmailNotifier()
        with patch("smtplib.SMTP") as mock_cls:
            mock_cls.return_value = MagicMock()
            await n.send_checkpoint_request(run_id="r1", checkpoint_name="cp1", summary="test")

    async def test_email_send_complete_does_not_raise(self) -> None:
        n = EmailNotifier()
        with patch("smtplib.SMTP") as mock_cls:
            mock_cls.return_value = MagicMock()
            await n.send_pipeline_complete(run_id="r1", summary="done")

    async def test_email_send_error_does_not_raise(self) -> None:
        n = EmailNotifier()
        with patch("smtplib.SMTP") as mock_cls:
            mock_cls.return_value = MagicMock()
            await n.send_error(run_id="r1", error="boom")
