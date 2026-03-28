"""E2E tests for event sources."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path  # noqa: TC003

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from regulatory_agent_kit.event_sources.file import FileEventSource
from regulatory_agent_kit.event_sources.webhook import WebhookEventSource
from regulatory_agent_kit.models.events import RegulatoryEvent  # noqa: TC001
from tests.helpers import make_event_dict as _make_event_dict


@pytest.mark.integration
class TestE2EEventSources:
    """End-to-end tests for file and webhook event sources."""

    async def test_file_source_full_cycle(self, tmp_path: Path) -> None:
        """Drop JSON -> callback fires -> file deleted."""
        received: list[RegulatoryEvent] = []

        async def on_event(event: RegulatoryEvent) -> None:
            received.append(event)

        source = FileEventSource(watch_dir=tmp_path, callback=on_event)

        event_file = tmp_path / "event-001.json"
        event_file.write_text(json.dumps(_make_event_dict()), encoding="utf-8")

        await source._scan_once()

        assert len(received) == 1
        assert received[0].regulation_id == "test-reg-001"
        assert not event_file.exists(), "File should be deleted after processing"

    async def test_file_source_ignores_non_json(self, tmp_path: Path) -> None:
        """Non-.json files produce no callback."""
        received: list[RegulatoryEvent] = []

        async def on_event(event: RegulatoryEvent) -> None:
            received.append(event)

        source = FileEventSource(watch_dir=tmp_path, callback=on_event)

        txt_file = tmp_path / "notes.txt"
        txt_file.write_text("not a json event", encoding="utf-8")

        await source._scan_once()

        assert len(received) == 0
        assert txt_file.exists(), "Non-JSON file should not be deleted"

    async def test_file_source_skips_malformed_json(self, tmp_path: Path) -> None:
        """Malformed JSON files produce no callback."""
        received: list[RegulatoryEvent] = []

        async def on_event(event: RegulatoryEvent) -> None:
            received.append(event)

        source = FileEventSource(watch_dir=tmp_path, callback=on_event)

        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{invalid json!!!", encoding="utf-8")

        await source._scan_once()

        assert len(received) == 0

    async def test_webhook_hmac_full_cycle(self) -> None:
        """Valid HMAC signature -> 202, callback fires."""
        received: list[RegulatoryEvent] = []

        async def on_event(event: RegulatoryEvent) -> None:
            received.append(event)

        webhook_app = FastAPI()
        secret = "my-webhook-secret"  # noqa: S105
        WebhookEventSource(webhook_app, on_event, secret=secret)

        body = json.dumps(_make_event_dict()).encode("utf-8")
        signature = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

        transport = ASGITransport(app=webhook_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/events",
                content=body,
                headers={
                    "X-Signature": signature,
                    "Content-Type": "application/json",
                },
            )
            assert resp.status_code == 202

        assert len(received) == 1
        assert received[0].regulation_id == "test-reg-001"

    async def test_webhook_rejects_invalid_hmac(self) -> None:
        """Wrong HMAC -> 403."""
        received: list[RegulatoryEvent] = []

        async def on_event(event: RegulatoryEvent) -> None:
            received.append(event)

        webhook_app = FastAPI()
        WebhookEventSource(webhook_app, on_event, secret="correct-secret")  # noqa: S106

        body = json.dumps(_make_event_dict()).encode("utf-8")
        wrong_signature = "sha256=" + hmac.new(b"wrong-secret", body, hashlib.sha256).hexdigest()

        transport = ASGITransport(app=webhook_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/events",
                content=body,
                headers={
                    "X-Signature": wrong_signature,
                    "Content-Type": "application/json",
                },
            )
            assert resp.status_code == 403

        assert len(received) == 0

    async def test_webhook_rejects_missing_hmac(self) -> None:
        """No X-Signature header -> 401."""
        received: list[RegulatoryEvent] = []

        async def on_event(event: RegulatoryEvent) -> None:
            received.append(event)

        webhook_app = FastAPI()
        WebhookEventSource(webhook_app, on_event, secret="some-secret")  # noqa: S106

        body = json.dumps(_make_event_dict()).encode("utf-8")

        transport = ASGITransport(app=webhook_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/events",
                content=body,
                headers={"Content-Type": "application/json"},
            )
            assert resp.status_code == 401

        assert len(received) == 0
