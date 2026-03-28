"""Webhook event source — FastAPI endpoint that validates HMAC signatures."""

from __future__ import annotations

import hashlib
import hmac
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import ValidationError

from regulatory_agent_kit.exceptions import EventSourceError
from regulatory_agent_kit.models.events import RegulatoryEvent

logger = logging.getLogger(__name__)

EventCallback = Callable[[RegulatoryEvent], Coroutine[Any, Any, None]]


class WebhookEventSource:
    """Exposes a ``POST /events`` endpoint with HMAC-SHA256 signature verification.

    The expected signature header is ``X-Signature`` and must equal
    ``sha256=<hex-digest>`` computed over the raw request body using the
    shared *secret*.
    """

    SIGNATURE_HEADER = "X-Signature"

    def __init__(
        self,
        app: FastAPI,
        callback: EventCallback,
        *,
        secret: str,
    ) -> None:
        if not secret:
            msg = "Webhook secret must not be empty."
            raise EventSourceError(msg)
        self._app = app
        self._callback = callback
        self._secret = secret.encode("utf-8")
        self._register_route()

    # ------------------------------------------------------------------
    # EventSource protocol
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """No-op — the route is registered on construction."""

    async def stop(self) -> None:
        """No-op — the lifecycle is managed by the FastAPI server."""

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _register_route(self) -> None:
        """Attach the ``POST /events`` endpoint to the FastAPI app."""

        @self._app.post("/events", status_code=202)
        async def _receive_event(request: Request) -> Response:
            body = await request.body()
            self._verify_signature(request, body)

            try:
                data = RegulatoryEvent.model_validate_json(body)
            except ValidationError as exc:
                raise HTTPException(
                    status_code=422,
                    detail=str(exc),
                ) from exc

            await self._callback(data)
            return Response(status_code=202)

    def _verify_signature(self, request: Request, body: bytes) -> None:
        """Validate the HMAC-SHA256 signature header."""
        sig_header = request.headers.get(self.SIGNATURE_HEADER)
        if sig_header is None:
            raise HTTPException(status_code=401, detail="Missing signature header.")

        expected = "sha256=" + hmac.new(self._secret, body, hashlib.sha256).hexdigest()

        if not hmac.compare_digest(sig_header, expected):
            raise HTTPException(status_code=403, detail="Invalid signature.")
