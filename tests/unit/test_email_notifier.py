"""Tests for EmailNotifier SMTP implementation."""

from __future__ import annotations

import smtplib
from unittest.mock import MagicMock, patch

import pytest

from regulatory_agent_kit.tools.notification import EmailNotifier


class TestEmailNotifierFormatting:
    """Test HTML email formatting methods."""

    def setup_method(self) -> None:
        """Create a notifier with sample configuration."""
        self.notifier = EmailNotifier(
            smtp_host="smtp.example.com",
            smtp_port=587,
            from_address="rak@example.com",
            to_addresses=["admin@example.com"],
        )

    def test_checkpoint_html_with_url(self) -> None:
        html = self.notifier._checkpoint_html(
            "run-123", "impact_review", "3 files affected", "https://example.com/approve"
        )
        assert "run-123" in html
        assert "impact_review" in html
        assert "3 files affected" in html
        assert "https://example.com/approve" in html
        assert "<a href=" in html

    def test_checkpoint_html_without_url(self) -> None:
        html = self.notifier._checkpoint_html("run-123", "merge_review", "Ready to merge", None)
        assert "run-123" in html
        assert "merge_review" in html
        assert "<a href=" not in html

    def test_complete_html(self) -> None:
        html = self.notifier._complete_html("run-456", "All repos processed")
        assert "run-456" in html
        assert "All repos processed" in html
        assert "Completed" in html

    def test_error_html(self) -> None:
        html = self.notifier._error_html("run-789", "Connection timeout")
        assert "run-789" in html
        assert "Connection timeout" in html
        assert "Error" in html
        assert "<pre>" in html


class TestEmailNotifierSending:
    """Test actual SMTP sending logic."""

    def setup_method(self) -> None:
        """Create a notifier with full configuration including auth."""
        self.notifier = EmailNotifier(
            smtp_host="smtp.example.com",
            smtp_port=587,
            from_address="rak@example.com",
            to_addresses=["admin@example.com", "team@example.com"],
            username="user",
            password="pass",  # noqa: S106
            use_tls=True,
        )

    async def test_send_checkpoint_request(self) -> None:
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value = mock_server

            await self.notifier.send_checkpoint_request(
                run_id="run-123456",
                checkpoint_name="impact_review",
                summary="3 files need review",
                approve_url="https://example.com/approve",
            )

            mock_smtp_cls.assert_called_once_with("smtp.example.com", 587, timeout=30)
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with("user", "pass")
            mock_server.sendmail.assert_called_once()
            args = mock_server.sendmail.call_args
            assert args[0][0] == "rak@example.com"
            assert args[0][1] == ["admin@example.com", "team@example.com"]
            # Verify the email body contains expected content
            email_body = args[0][2]
            assert "impact_review" in email_body
            mock_server.quit.assert_called_once()

    async def test_send_pipeline_complete(self) -> None:
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value = mock_server

            await self.notifier.send_pipeline_complete(
                run_id="run-456789",
                summary="All done",
            )

            mock_server.sendmail.assert_called_once()
            email_body = mock_server.sendmail.call_args[0][2]
            assert "Completed" in email_body

    async def test_send_error(self) -> None:
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value = mock_server

            await self.notifier.send_error(
                run_id="run-789012",
                error="Something broke",
            )

            mock_server.sendmail.assert_called_once()
            email_body = mock_server.sendmail.call_args[0][2]
            assert "Something broke" in email_body

    async def test_send_without_tls(self) -> None:
        self.notifier.use_tls = False
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value = mock_server

            await self.notifier.send_pipeline_complete(
                run_id="run-100000",
                summary="Done",
            )

            mock_server.starttls.assert_not_called()

    async def test_send_without_auth(self) -> None:
        self.notifier.username = ""
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value = mock_server

            await self.notifier.send_pipeline_complete(
                run_id="run-200000",
                summary="Done",
            )

            mock_server.login.assert_not_called()

    async def test_smtp_error_propagates(self) -> None:
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value = mock_server
            mock_server.sendmail.side_effect = smtplib.SMTPException("Connection refused")

            with pytest.raises(smtplib.SMTPException, match="Connection refused"):
                await self.notifier.send_error(
                    run_id="run-err",
                    error="test",
                )

    async def test_quit_called_on_sendmail_failure(self) -> None:
        """Verify server.quit() is called even when sendmail raises."""
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value = mock_server
            mock_server.sendmail.side_effect = smtplib.SMTPException("fail")

            with pytest.raises(smtplib.SMTPException):
                await self.notifier.send_error(run_id="run-err", error="test")

            mock_server.quit.assert_called_once()

    async def test_email_subject_contains_run_id_prefix(self) -> None:
        """Verify email subject uses first 8 chars of run_id."""
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value = mock_server

            await self.notifier.send_checkpoint_request(
                run_id="abcdefghijklmnop",
                checkpoint_name="merge_review",
                summary="test",
            )

            email_body = mock_server.sendmail.call_args[0][2]
            assert "abcdefgh" in email_body
            assert "merge_review" in email_body

    async def test_email_headers(self) -> None:
        """Verify From and To headers are set correctly."""
        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_server = MagicMock()
            mock_smtp_cls.return_value = mock_server

            await self.notifier.send_pipeline_complete(
                run_id="run-hdr",
                summary="test",
            )

            email_body = mock_server.sendmail.call_args[0][2]
            assert "From: rak@example.com" in email_body
            assert "To: admin@example.com, team@example.com" in email_body


class TestEmailNotifierDataclass:
    """Test dataclass field defaults and custom values."""

    def test_default_values(self) -> None:
        notifier = EmailNotifier()
        assert notifier.smtp_host == "localhost"
        assert notifier.smtp_port == 587
        assert notifier.from_address == ""
        assert notifier.to_addresses == []
        assert notifier.username == ""
        assert notifier.password == ""
        assert notifier.use_tls is True

    def test_custom_values(self) -> None:
        notifier = EmailNotifier(
            smtp_host="mail.example.com",
            smtp_port=465,
            from_address="noreply@example.com",
            to_addresses=["team@example.com"],
            username="apikey",
            password="secret",  # noqa: S106
            use_tls=False,
        )
        assert notifier.smtp_host == "mail.example.com"
        assert notifier.smtp_port == 465
        assert notifier.from_address == "noreply@example.com"
        assert notifier.to_addresses == ["team@example.com"]
        assert notifier.username == "apikey"
        assert notifier.password == "secret"  # noqa: S105
        assert notifier.use_tls is False
