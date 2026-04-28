"""Custom middleware for the RAK FastAPI application."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

import jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request  # noqa: TC002
from starlette.responses import JSONResponse, Response

if TYPE_CHECKING:
    from regulatory_agent_kit.config import AuthSettings

logger = logging.getLogger(__name__)

# Paths that never require authentication.
_PUBLIC_PATHS: frozenset[str] = frozenset({"/health"})


# ---------------------------------------------------------------------------
# JWKS cache helpers
# ---------------------------------------------------------------------------

_jwks_cache: dict[str, Any] = {}


def _fetch_jwks(jwks_url: str) -> dict[str, Any]:
    """Fetch JWKS from the given URL, with a simple in-process cache.

    Uses ``urllib.request`` so we don't add ``httpx`` as a runtime
    dependency of the middleware (httpx is dev-only for tests).
    """
    if jwks_url in _jwks_cache:
        return cast("dict[str, Any]", _jwks_cache[jwks_url])

    import json
    import urllib.request

    with urllib.request.urlopen(jwks_url) as resp:  # noqa: S310
        data: dict[str, Any] = json.loads(resp.read())

    _jwks_cache[jwks_url] = data
    return data


def clear_jwks_cache() -> None:
    """Clear the in-process JWKS cache (useful in tests)."""
    _jwks_cache.clear()


def _build_rs256_key_from_jwks(jwks_data: dict[str, Any]) -> jwt.algorithms.RSAAlgorithm:
    """Extract the first RS256-compatible key from a JWKS payload."""
    for key_dict in jwks_data.get("keys", []):
        if key_dict.get("kty") == "RSA" and key_dict.get("use", "sig") == "sig":
            return jwt.algorithms.RSAAlgorithm.from_jwk(key_dict)  # type: ignore[return-value]
    msg = "No suitable RSA signing key found in JWKS"
    raise ValueError(msg)


# ---------------------------------------------------------------------------
# Bearer-token middleware
# ---------------------------------------------------------------------------


class RakAuthMiddleware(BaseHTTPMiddleware):
    """Simple Bearer-token authentication middleware.

    Skips authentication for the ``/health`` endpoint so that
    load-balancer probes work without credentials.

    The expected token is stored on ``app.state.api_token``.  If the
    token is not configured (``None`` or empty string), *all* requests
    are allowed through -- this keeps the development experience smooth.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Validate the ``Authorization: Bearer <token>`` header."""
        # Always allow health checks.
        if request.url.path in _PUBLIC_PATHS:
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


# ---------------------------------------------------------------------------
# JWT middleware
# ---------------------------------------------------------------------------


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """JWT-based authentication middleware.

    Validates ``Authorization: Bearer <jwt>`` headers, decodes the JWT,
    and attaches the decoded claims to ``request.state.user_claims``.

    Supports HS256 (shared secret) and RS256 (public key or JWKS URL).
    """

    def __init__(self, app: Any, auth_settings: AuthSettings) -> None:
        super().__init__(app)
        self._settings = auth_settings

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Extract, validate, and decode the JWT from the Authorization header."""
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or malformed Authorization header."},
            )

        token = auth_header.removeprefix("Bearer ").strip()
        if not token:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or malformed Authorization header."},
            )

        try:
            claims = self._decode_token(token)
        except jwt.ExpiredSignatureError:
            return JSONResponse(
                status_code=401,
                content={"detail": "Token has expired."},
            )
        except jwt.InvalidTokenError as exc:
            logger.debug("JWT validation failed: %s", exc)
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid token."},
            )

        # Attach decoded claims to request state for downstream use.
        request.state.user_claims = {
            "sub": claims.get("sub", ""),
            "email": claims.get("email", ""),
            "roles": claims.get("roles", []),
            **{k: v for k, v in claims.items() if k not in ("sub", "email", "roles")},
        }

        return await call_next(request)

    def _decode_token(self, token: str) -> dict[str, Any]:
        """Decode and validate a JWT token according to the configured algorithm."""
        algorithm = self._settings.jwt_algorithm
        key = self._resolve_key(algorithm)

        decode_options: dict[str, Any] = {"algorithms": [algorithm]}
        if self._settings.jwt_issuer:
            decode_options["issuer"] = self._settings.jwt_issuer
        if self._settings.jwt_audience:
            decode_options["audience"] = self._settings.jwt_audience

        result: dict[str, Any] = jwt.decode(token, key, **decode_options)
        return result

    def _resolve_key(self, algorithm: str) -> Any:
        """Return the verification key for the given algorithm."""
        if algorithm == "HS256":
            if not self._settings.jwt_secret:
                msg = "jwt_secret is required for HS256 algorithm"
                raise jwt.InvalidTokenError(msg)
            return self._settings.jwt_secret

        if algorithm == "RS256":
            if self._settings.jwt_jwks_url:
                jwks_data = _fetch_jwks(self._settings.jwt_jwks_url)
                return _build_rs256_key_from_jwks(jwks_data)
            if self._settings.jwt_public_key:
                return self._settings.jwt_public_key
            msg = "jwt_public_key or jwt_jwks_url is required for RS256 algorithm"
            raise jwt.InvalidTokenError(msg)

        msg = f"Unsupported JWT algorithm: {algorithm}"
        raise jwt.InvalidTokenError(msg)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def add_auth_middleware(app: Any, auth_settings: AuthSettings) -> None:
    """Add the appropriate auth middleware to *app* based on *auth_settings*.

    Auth modes:
    - ``none``   -- no middleware added; all requests pass through.
    - ``bearer`` -- static bearer-token check via ``RakAuthMiddleware``.
    - ``jwt``    -- JWT validation via ``JWTAuthMiddleware``.
    """
    mode = auth_settings.mode.lower()
    if mode == "none":
        return
    if mode == "bearer":
        app.add_middleware(RakAuthMiddleware)
        app.state.api_token = auth_settings.bearer_token
    elif mode == "jwt":
        app.add_middleware(JWTAuthMiddleware, auth_settings=auth_settings)
    else:
        msg = f"Unknown auth mode: {mode!r}. Expected 'none', 'bearer', or 'jwt'."
        raise ValueError(msg)
