"""Custom middleware for the RAK FastAPI application."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request  # noqa: TC002
from starlette.responses import JSONResponse, Response


class RakAuthMiddleware(BaseHTTPMiddleware):
    """Simple Bearer-token authentication middleware.

    Skips authentication for the ``/health`` endpoint so that
    load-balancer probes work without credentials.

    The expected token is stored on ``app.state.api_token``.  If the
    token is not configured (``None`` or empty string), *all* requests
    are allowed through — this keeps the development experience smooth.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Validate the ``Authorization: Bearer <token>`` header."""
        # Always allow health checks.
        if request.url.path == "/health":
            return await call_next(request)

        expected_token: str | None = getattr(request.app.state, "api_token", None)

        # If no token is configured, skip authentication entirely.
        if not expected_token:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or malformed Authorization header."},
            )

        provided_token = auth_header.removeprefix("Bearer ").strip()
        if provided_token != expected_token:
            return JSONResponse(
                status_code=403,
                content={"detail": "Invalid API token."},
            )

        return await call_next(request)
