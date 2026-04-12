"""Unit tests for WebhookEventSource."""

from __future__ import annotations

import hashlib
import hmac
import json
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from regulatory_agent_kit.event_sources.webhook import WebhookEventSource
from regulatory_agent_kit.exceptions import EventSourceError
from regulatory_agent_kit.models.events import RegulatoryEvent

_SECRET = "test-webhook-secret"  # noqa: S105


def _valid_event_data() -> dict[str, str]:
    return {
        "regulation_id": "example-regulation-2025",
        "change_type": "new_requirement",
        "source": "webhook",
    }


def _sign(body: bytes, secret: str = _SECRET) -> str:
    """Compute the expected HMAC-SHA256 signature."""
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


@pytest.fixture
def webhook_app() -> tuple[FastAPI, AsyncMock]:
    """Return a FastAPI app with a WebhookEventSource attached."""
    app = FastAPI()
    callback = AsyncMock()
    WebhookEventSource(app, callback, secret=_SECRET)
    return app, callback


class TestWebhookEventSource:
    """Tests for the webhook event source."""

    async def test_valid_request_produces_event(
        self, webhook_app: tuple[FastAPI, AsyncMock]
    ) -> None:
        app, callback = webhook_app
        body = json.dumps(_valid_event_data()).encode()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/events",
                content=body,
                headers={
                    "X-Signature": _sign(body),
                    "Content-Type": "application/json",
                },
            )

        assert resp.status_code == 202
        callback.assert_called_once()
        event = callback.call_args[0][0]
        assert isinstance(event, RegulatoryEvent)
        assert event.regulation_id == "example-regulation-2025"

    async def test_missing_signature_returns_401(
        self, webhook_app: tuple[FastAPI, AsyncMock]
    ) -> None:
        app, callback = webhook_app
        body = json.dumps(_valid_event_data()).encode()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/events",
                content=body,
                headers={"Content-Type": "application/json"},
            )

        assert resp.status_code == 401
        callback.assert_not_called()

    async def test_wrong_signature_returns_403(
        self, webhook_app: tuple[FastAPI, AsyncMock]
    ) -> None:
        app, callback = webhook_app
        body = json.dumps(_valid_event_data()).encode()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/events",
                content=body,
                headers={
                    "X-Signature": "sha256=deadbeef",
                    "Content-Type": "application/json",
                },
            )

        assert resp.status_code == 403
        callback.assert_not_called()

    async def test_invalid_json_body_returns_422(
        self, webhook_app: tuple[FastAPI, AsyncMock]
    ) -> None:
        app, callback = webhook_app
        body = json.dumps({"foo": "bar"}).encode()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/events",
                content=body,
                headers={
                    "X-Signature": _sign(body),
                    "Content-Type": "application/json",
                },
            )

        assert resp.status_code == 422
        callback.assert_not_called()

    async def test_empty_secret_raises(self) -> None:
        app = FastAPI()
        callback = AsyncMock()
        with pytest.raises(EventSourceError, match="secret must not be empty"):
            WebhookEventSource(app, callback, secret="")

    async def test_start_stop_are_noop(self) -> None:
        source = WebhookEventSource(
            FastAPI(),
            AsyncMock(),
            secret="s",  # noqa: S106
        )
        await source.start()
        await source.stop()
