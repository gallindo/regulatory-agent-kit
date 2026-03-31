"""Tests for Kafka credential rotation and CredentialReloader."""

from __future__ import annotations

import asyncio
import json
import threading
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from regulatory_agent_kit.event_sources.kafka import (
    CredentialReloader,
    KafkaConfig,
    KafkaEventSource,
)
from regulatory_agent_kit.exceptions import EventSourceError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_credentials(path: str, username: str, password: str) -> None:
    """Write a JSON credentials file."""
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"username": username, "password": password}, fh)


# ---------------------------------------------------------------------------
# CredentialReloader — file change detection
# ---------------------------------------------------------------------------


class TestCredentialReloaderDetectsChanges:
    """CredentialReloader.check_for_update detects file modifications."""

    def test_detects_file_change(self, tmp_path: Any) -> None:
        cred_file = str(tmp_path / "creds.json")
        _write_credentials(cred_file, "user1", "pass1")

        captured: list[tuple[str, str]] = []
        reloader = CredentialReloader(
            credential_path=cred_file,
            on_rotate=lambda u, p: captured.append((u, p)),
        )
        # First call records initial mtime and triggers callback.
        assert reloader.check_for_update() is True
        assert captured == [("user1", "pass1")]

    def test_ignores_unchanged_file(self, tmp_path: Any) -> None:
        cred_file = str(tmp_path / "creds.json")
        _write_credentials(cred_file, "user1", "pass1")

        captured: list[tuple[str, str]] = []
        reloader = CredentialReloader(
            credential_path=cred_file,
            on_rotate=lambda u, p: captured.append((u, p)),
        )
        reloader.check_for_update()  # first call — records mtime
        captured.clear()

        # Second call with no file change should return False.
        assert reloader.check_for_update() is False
        assert captured == []

    def test_detects_second_change(self, tmp_path: Any) -> None:
        cred_file = str(tmp_path / "creds.json")
        _write_credentials(cred_file, "user1", "pass1")

        captured: list[tuple[str, str]] = []
        reloader = CredentialReloader(
            credential_path=cred_file,
            on_rotate=lambda u, p: captured.append((u, p)),
        )
        reloader.check_for_update()
        captured.clear()

        # Bump mtime so the change is detected.
        time.sleep(0.05)
        _write_credentials(cred_file, "user2", "pass2")

        assert reloader.check_for_update() is True
        assert captured == [("user2", "pass2")]

    def test_returns_false_for_missing_file(self) -> None:
        reloader = CredentialReloader(
            credential_path="/nonexistent/path/creds.json",
            on_rotate=lambda u, p: None,
        )
        assert reloader.check_for_update() is False

    def test_raises_on_invalid_json(self, tmp_path: Any) -> None:
        cred_file = str(tmp_path / "creds.json")
        with open(cred_file, "w", encoding="utf-8") as fh:
            fh.write("not json")

        reloader = CredentialReloader(
            credential_path=cred_file,
            on_rotate=lambda u, p: None,
        )
        # check_for_update logs a warning and returns False (does not raise).
        assert reloader.check_for_update() is False

    def test_raises_on_missing_keys(self, tmp_path: Any) -> None:
        cred_file = str(tmp_path / "creds.json")
        with open(cred_file, "w", encoding="utf-8") as fh:
            json.dump({"username": "only_user"}, fh)

        reloader = CredentialReloader(
            credential_path=cred_file,
            on_rotate=lambda u, p: None,
        )
        assert reloader.check_for_update() is False


# ---------------------------------------------------------------------------
# CredentialReloader — async watch lifecycle
# ---------------------------------------------------------------------------


class TestCredentialReloaderWatchLifecycle:
    """start() and stop() manage the async polling task."""

    async def test_start_and_stop(self, tmp_path: Any) -> None:
        cred_file = str(tmp_path / "creds.json")
        _write_credentials(cred_file, "user1", "pass1")

        reloader = CredentialReloader(
            credential_path=cred_file,
            on_rotate=lambda u, p: None,
            poll_interval=0.05,
        )
        await reloader.start()
        assert reloader._task is not None
        assert not reloader._task.done()

        await reloader.stop()
        assert reloader._task is None

    async def test_stop_is_idempotent(self, tmp_path: Any) -> None:
        cred_file = str(tmp_path / "creds.json")
        _write_credentials(cred_file, "user1", "pass1")

        reloader = CredentialReloader(
            credential_path=cred_file,
            on_rotate=lambda u, p: None,
        )
        # Stopping without starting should be fine.
        await reloader.stop()
        assert reloader._task is None

    async def test_watch_loop_detects_change(self, tmp_path: Any) -> None:
        cred_file = str(tmp_path / "creds.json")
        _write_credentials(cred_file, "user1", "pass1")

        captured: list[tuple[str, str]] = []
        reloader = CredentialReloader(
            credential_path=cred_file,
            on_rotate=lambda u, p: captured.append((u, p)),
            poll_interval=0.05,
        )
        await reloader.start()

        # Modify the file so the watch loop picks it up.
        time.sleep(0.05)
        _write_credentials(cred_file, "rotated_user", "rotated_pass")
        await asyncio.sleep(0.2)

        await reloader.stop()
        assert ("rotated_user", "rotated_pass") in captured


# ---------------------------------------------------------------------------
# KafkaEventSource.rotate_credentials
# ---------------------------------------------------------------------------


class TestKafkaEventSourceRotateCredentials:
    """rotate_credentials updates consumer config and reconnects."""

    def _make_source(self) -> KafkaEventSource:
        config = KafkaConfig(
            topic="test-topic",
            consumer_config={
                "bootstrap.servers": "localhost:9092",
                "group.id": "test-group",
                "auto.offset.reset": "earliest",
            },
        )
        callback = MagicMock()
        return KafkaEventSource(config=config, callback=callback)

    def test_updates_config_with_new_credentials(self) -> None:
        source = self._make_source()
        source.rotate_credentials("new_user", "new_pass")

        assert source._config.consumer_config["sasl.username"] == "new_user"
        assert source._config.consumer_config["sasl.password"] == "new_pass"
        # Original keys preserved.
        assert source._config.consumer_config["bootstrap.servers"] == "localhost:9092"

    def test_preserves_topic_and_poll_timeout(self) -> None:
        source = self._make_source()
        source.rotate_credentials("u", "p")

        assert source._config.topic == "test-topic"
        assert source._config.poll_timeout == 1.0

    @patch(
        "regulatory_agent_kit.event_sources.kafka._HAS_KAFKA",
        True,
    )
    @patch("regulatory_agent_kit.event_sources.kafka.Consumer")
    def test_reconnects_consumer_when_running(self, mock_consumer_cls: MagicMock) -> None:
        source = self._make_source()
        old_consumer = MagicMock()
        source._consumer = old_consumer

        source.rotate_credentials("rotated_user", "rotated_pass")

        old_consumer.close.assert_called_once()
        mock_consumer_cls.assert_called_once_with(source._config.consumer_config)
        mock_consumer_cls.return_value.subscribe.assert_called_once_with(["test-topic"])
        assert source._consumer is mock_consumer_cls.return_value

    def test_no_reconnect_when_consumer_is_none(self) -> None:
        source = self._make_source()
        assert source._consumer is None
        source.rotate_credentials("u", "p")
        # Should not raise; consumer stays None.
        assert source._consumer is None

    def test_thread_safety(self) -> None:
        """Multiple threads can call rotate_credentials concurrently."""
        source = self._make_source()
        errors: list[Exception] = []

        def rotate(idx: int) -> None:
            try:
                source.rotate_credentials(f"user_{idx}", f"pass_{idx}")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=rotate, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        # Config should have one of the rotated credentials.
        assert "sasl.username" in source._config.consumer_config
        assert "sasl.password" in source._config.consumer_config


# ---------------------------------------------------------------------------
# KafkaEventSource — credential watch integration
# ---------------------------------------------------------------------------


class TestKafkaEventSourceCredentialWatch:
    """start_credential_watch / stop_credential_watch lifecycle."""

    async def test_start_and_stop_credential_watch(self, tmp_path: Any) -> None:
        cred_file = str(tmp_path / "creds.json")
        _write_credentials(cred_file, "user1", "pass1")

        config = KafkaConfig(topic="t")
        source = KafkaEventSource(config=config, callback=MagicMock())

        await source.start_credential_watch(cred_file, poll_interval=0.05)
        assert source._credential_reloader is not None

        await source.stop_credential_watch()
        assert source._credential_reloader is None

    async def test_restart_credential_watch_stops_old(self, tmp_path: Any) -> None:
        cred_file = str(tmp_path / "creds.json")
        _write_credentials(cred_file, "user1", "pass1")

        config = KafkaConfig(topic="t")
        source = KafkaEventSource(config=config, callback=MagicMock())

        await source.start_credential_watch(cred_file, poll_interval=0.05)
        first_reloader = source._credential_reloader

        await source.start_credential_watch(cred_file, poll_interval=0.05)
        # Old reloader should have been stopped; new one created.
        assert source._credential_reloader is not first_reloader

        await source.stop_credential_watch()

    async def test_stop_includes_credential_watch(self, tmp_path: Any) -> None:
        """Calling stop() on the event source also stops credential watch."""
        cred_file = str(tmp_path / "creds.json")
        _write_credentials(cred_file, "user1", "pass1")

        config = KafkaConfig(topic="t")
        source = KafkaEventSource(config=config, callback=MagicMock())

        await source.start_credential_watch(cred_file, poll_interval=0.05)
        await source.stop()
        assert source._credential_reloader is None


# ---------------------------------------------------------------------------
# CredentialReloader._read_credentials edge cases
# ---------------------------------------------------------------------------


class TestReadCredentials:
    """Direct tests for _read_credentials validation."""

    def test_valid_file(self, tmp_path: Any) -> None:
        cred_file = str(tmp_path / "creds.json")
        _write_credentials(cred_file, "u", "p")
        reloader = CredentialReloader(credential_path=cred_file, on_rotate=lambda u, p: None)
        assert reloader._read_credentials() == ("u", "p")

    def test_missing_file_raises(self) -> None:
        reloader = CredentialReloader(
            credential_path="/does/not/exist.json", on_rotate=lambda u, p: None
        )
        with pytest.raises(EventSourceError, match="Failed to read"):
            reloader._read_credentials()

    def test_empty_username_raises(self, tmp_path: Any) -> None:
        cred_file = str(tmp_path / "creds.json")
        with open(cred_file, "w", encoding="utf-8") as fh:
            json.dump({"username": "", "password": "p"}, fh)
        reloader = CredentialReloader(credential_path=cred_file, on_rotate=lambda u, p: None)
        with pytest.raises(EventSourceError, match="must contain"):
            reloader._read_credentials()

    def test_empty_password_raises(self, tmp_path: Any) -> None:
        cred_file = str(tmp_path / "creds.json")
        with open(cred_file, "w", encoding="utf-8") as fh:
            json.dump({"username": "u", "password": ""}, fh)
        reloader = CredentialReloader(credential_path=cred_file, on_rotate=lambda u, p: None)
        with pytest.raises(EventSourceError, match="must contain"):
            reloader._read_credentials()
