"""Unit tests for JWT authentication middleware (feature #11)."""

from __future__ import annotations

import time
from typing import Any

import httpx
import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
)
from fastapi import FastAPI
from starlette.requests import Request  # noqa: TC002

from regulatory_agent_kit.api.middleware import (
    JWTAuthMiddleware,
    RakAuthMiddleware,
    _build_rs256_key_from_jwks,
    add_auth_middleware,
    clear_jwks_cache,
)
from regulatory_agent_kit.config import AuthSettings

# ---------------------------------------------------------------------------
# RSA key-pair fixture (generated once per module for speed)
# ---------------------------------------------------------------------------

_RSA_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_RSA_PUBLIC_KEY = _RSA_PRIVATE_KEY.public_key()

_RSA_PUBLIC_PEM = _RSA_PUBLIC_KEY.public_bytes(
    Encoding.PEM,
    PublicFormat.SubjectPublicKeyInfo,
).decode()

HS256_SECRET = "test-secret-key-for-unit-tests-minimum-length"  # noqa: S105


# ---------------------------------------------------------------------------
# Helper: minimal FastAPI app with a protected endpoint
# ---------------------------------------------------------------------------


def _make_app() -> FastAPI:
    """Create a minimal FastAPI app with a protected endpoint and health check."""
    test_app = FastAPI()

    @test_app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @test_app.get("/protected")
    async def protected(request: Request) -> dict[str, Any]:
        claims = getattr(request.state, "user_claims", None)
        return {"claims": claims}

    return test_app


def _make_hs256_token(
    payload: dict[str, Any],
    secret: str = HS256_SECRET,
) -> str:
    """Encode a JWT with HS256."""
    return pyjwt.encode(payload, secret, algorithm="HS256")


def _make_rs256_token(payload: dict[str, Any]) -> str:
    """Encode a JWT with RS256 using the test private key."""
    return pyjwt.encode(payload, _RSA_PRIVATE_KEY, algorithm="RS256")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_jwks() -> None:
    """Reset JWKS cache between tests."""
    clear_jwks_cache()


@pytest.fixture
def hs256_settings() -> AuthSettings:
    return AuthSettings(
        mode="jwt",
        jwt_algorithm="HS256",
        jwt_secret=HS256_SECRET,
    )


@pytest.fixture
def rs256_settings() -> AuthSettings:
    return AuthSettings(
        mode="jwt",
        jwt_algorithm="RS256",
        jwt_public_key=_RSA_PUBLIC_PEM,
    )


@pytest.fixture
def hs256_app(hs256_settings: AuthSettings) -> FastAPI:
    test_app = _make_app()
    test_app.add_middleware(JWTAuthMiddleware, auth_settings=hs256_settings)
    return test_app


@pytest.fixture
def rs256_app(rs256_settings: AuthSettings) -> FastAPI:
    test_app = _make_app()
    test_app.add_middleware(JWTAuthMiddleware, auth_settings=rs256_settings)
    return test_app


@pytest.fixture
def hs256_client(hs256_app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=hs256_app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


@pytest.fixture
def rs256_client(rs256_app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=rs256_app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


# ---------------------------------------------------------------------------
# Tests: HS256
# ---------------------------------------------------------------------------


async def test_valid_hs256_token_accepted(hs256_client: httpx.AsyncClient) -> None:
    token = _make_hs256_token({"sub": "user-1", "email": "a@b.com", "roles": ["admin"]})
    resp = await hs256_client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    claims = resp.json()["claims"]
    assert claims["sub"] == "user-1"
    assert claims["email"] == "a@b.com"
    assert claims["roles"] == ["admin"]


async def test_expired_token_rejected(hs256_client: httpx.AsyncClient) -> None:
    token = _make_hs256_token({"sub": "user-1", "exp": int(time.time()) - 60})
    resp = await hs256_client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert "expired" in resp.json()["detail"].lower()


async def test_invalid_signature_rejected(hs256_client: httpx.AsyncClient) -> None:
    token = _make_hs256_token({"sub": "user-1"}, secret="wrong-secret-entirely")  # noqa: S106
    resp = await hs256_client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert "invalid" in resp.json()["detail"].lower()


async def test_missing_token_returns_401(hs256_client: httpx.AsyncClient) -> None:
    resp = await hs256_client.get("/protected")
    assert resp.status_code == 401
    assert "missing" in resp.json()["detail"].lower()


async def test_malformed_auth_header(hs256_client: httpx.AsyncClient) -> None:
    resp = await hs256_client.get("/protected", headers={"Authorization": "Basic abc123"})
    assert resp.status_code == 401


async def test_empty_bearer_token(hs256_client: httpx.AsyncClient) -> None:
    resp = await hs256_client.get("/protected", headers={"Authorization": "Bearer "})
    assert resp.status_code == 401


async def test_claims_extracted_correctly(hs256_client: httpx.AsyncClient) -> None:
    token = _make_hs256_token(
        {
            "sub": "u-42",
            "email": "test@example.com",
            "roles": ["viewer", "editor"],
            "org_id": "org-99",
        }
    )
    resp = await hs256_client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    claims = resp.json()["claims"]
    assert claims["sub"] == "u-42"
    assert claims["email"] == "test@example.com"
    assert claims["roles"] == ["viewer", "editor"]
    assert claims["org_id"] == "org-99"


async def test_missing_optional_claims_default(hs256_client: httpx.AsyncClient) -> None:
    """Tokens without sub/email/roles should still work, defaulting to empty values."""
    token = _make_hs256_token({"custom_field": "hello"})
    resp = await hs256_client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    claims = resp.json()["claims"]
    assert claims["sub"] == ""
    assert claims["email"] == ""
    assert claims["roles"] == []
    assert claims["custom_field"] == "hello"


async def test_health_endpoint_bypasses_jwt(hs256_client: httpx.AsyncClient) -> None:
    resp = await hs256_client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Tests: RS256
# ---------------------------------------------------------------------------


async def test_valid_rs256_token_accepted(rs256_client: httpx.AsyncClient) -> None:
    token = _make_rs256_token({"sub": "rs-user", "email": "rs@test.com", "roles": ["ops"]})
    resp = await rs256_client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    claims = resp.json()["claims"]
    assert claims["sub"] == "rs-user"
    assert claims["email"] == "rs@test.com"


async def test_rs256_rejects_hs256_token(rs256_client: httpx.AsyncClient) -> None:
    """An HS256-signed token must be rejected by an RS256-configured middleware."""
    token = _make_hs256_token({"sub": "hacker"})
    resp = await rs256_client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


async def test_rs256_rejects_wrong_key(rs256_client: httpx.AsyncClient) -> None:
    """A token signed with a different RS256 key must be rejected."""
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = pyjwt.encode({"sub": "intruder"}, other_key, algorithm="RS256")
    resp = await rs256_client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Tests: Issuer and audience validation
# ---------------------------------------------------------------------------


async def test_issuer_validation() -> None:
    settings = AuthSettings(
        mode="jwt",
        jwt_algorithm="HS256",
        jwt_secret=HS256_SECRET,
        jwt_issuer="https://auth.example.com",
    )
    test_app = _make_app()
    test_app.add_middleware(JWTAuthMiddleware, auth_settings=settings)
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=test_app), base_url="http://testserver"
    )

    # Valid issuer.
    good_token = _make_hs256_token({"sub": "u", "iss": "https://auth.example.com"})
    resp = await client.get("/protected", headers={"Authorization": f"Bearer {good_token}"})
    assert resp.status_code == 200

    # Wrong issuer.
    bad_token = _make_hs256_token({"sub": "u", "iss": "https://evil.com"})
    resp = await client.get("/protected", headers={"Authorization": f"Bearer {bad_token}"})
    assert resp.status_code == 401


async def test_audience_validation() -> None:
    settings = AuthSettings(
        mode="jwt",
        jwt_algorithm="HS256",
        jwt_secret=HS256_SECRET,
        jwt_audience="rak-api",
    )
    test_app = _make_app()
    test_app.add_middleware(JWTAuthMiddleware, auth_settings=settings)
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=test_app), base_url="http://testserver"
    )

    # Valid audience.
    good_token = _make_hs256_token({"sub": "u", "aud": "rak-api"})
    resp = await client.get("/protected", headers={"Authorization": f"Bearer {good_token}"})
    assert resp.status_code == 200

    # Wrong audience.
    bad_token = _make_hs256_token({"sub": "u", "aud": "other-api"})
    resp = await client.get("/protected", headers={"Authorization": f"Bearer {bad_token}"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Tests: add_auth_middleware factory
# ---------------------------------------------------------------------------


def test_add_auth_middleware_none_mode() -> None:
    """mode='none' should not add any middleware."""
    test_app = _make_app()
    initial_middleware_count = len(test_app.user_middleware)
    add_auth_middleware(test_app, AuthSettings(mode="none"))
    assert len(test_app.user_middleware) == initial_middleware_count


def test_add_auth_middleware_bearer_mode() -> None:
    """mode='bearer' should add the bearer-token middleware."""
    test_app = _make_app()
    add_auth_middleware(test_app, AuthSettings(mode="bearer", bearer_token="tok-123"))  # noqa: S106
    assert test_app.state.api_token == "tok-123"  # noqa: S105


def test_add_auth_middleware_jwt_mode() -> None:
    """mode='jwt' should add the JWT middleware."""
    test_app = _make_app()
    initial_count = len(test_app.user_middleware)
    add_auth_middleware(
        test_app,
        AuthSettings(mode="jwt", jwt_algorithm="HS256", jwt_secret=HS256_SECRET),
    )
    assert len(test_app.user_middleware) == initial_count + 1


def test_add_auth_middleware_unknown_mode() -> None:
    """Unknown auth mode should raise ValueError."""
    test_app = _make_app()
    with pytest.raises(ValueError, match="Unknown auth mode"):
        add_auth_middleware(test_app, AuthSettings(mode="invalid"))


# ---------------------------------------------------------------------------
# Tests: Bearer middleware (existing, kept for regression)
# ---------------------------------------------------------------------------


async def test_bearer_mode_accepts_valid_token() -> None:
    test_app = _make_app()
    test_app.add_middleware(RakAuthMiddleware)
    test_app.state.api_token = "my-secret-token"  # noqa: S105
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=test_app), base_url="http://testserver"
    )
    resp = await client.get("/protected", headers={"Authorization": "Bearer my-secret-token"})
    assert resp.status_code == 200


async def test_bearer_mode_rejects_wrong_token() -> None:
    test_app = _make_app()
    test_app.add_middleware(RakAuthMiddleware)
    test_app.state.api_token = "my-secret-token"  # noqa: S105
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=test_app), base_url="http://testserver"
    )
    resp = await client.get("/protected", headers={"Authorization": "Bearer wrong-token"})
    assert resp.status_code == 403


async def test_bearer_mode_no_token_configured_passes() -> None:
    """When no token is configured, bearer middleware lets everything through."""
    test_app = _make_app()
    test_app.add_middleware(RakAuthMiddleware)
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=test_app), base_url="http://testserver"
    )
    resp = await client.get("/protected")
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Tests: JWKS key extraction
# ---------------------------------------------------------------------------


def test_build_rs256_key_from_jwks_valid() -> None:
    """Should extract a public key from a well-formed JWKS payload."""
    jwk_dict = pyjwt.algorithms.RSAAlgorithm.to_jwk(_RSA_PUBLIC_KEY, as_dict=True)
    jwk_dict["use"] = "sig"
    jwk_dict["kty"] = "RSA"
    jwks_data: dict[str, Any] = {"keys": [jwk_dict]}

    key = _build_rs256_key_from_jwks(jwks_data)
    assert key is not None


def test_build_rs256_key_from_jwks_no_keys() -> None:
    """Should raise when JWKS has no suitable keys."""
    with pytest.raises(ValueError, match="No suitable RSA"):
        _build_rs256_key_from_jwks({"keys": []})


# ---------------------------------------------------------------------------
# Tests: Unsupported algorithm
# ---------------------------------------------------------------------------


async def test_unsupported_algorithm_returns_401() -> None:
    settings = AuthSettings(
        mode="jwt",
        jwt_algorithm="ES384",
        jwt_secret="irrelevant",  # noqa: S106
    )
    test_app = _make_app()
    test_app.add_middleware(JWTAuthMiddleware, auth_settings=settings)
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=test_app), base_url="http://testserver"
    )

    # Even a well-formed HS256 token should be rejected.
    token = _make_hs256_token({"sub": "x"})
    resp = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Tests: HS256 without secret configured
# ---------------------------------------------------------------------------


async def test_hs256_without_secret_returns_401() -> None:
    settings = AuthSettings(
        mode="jwt",
        jwt_algorithm="HS256",
        jwt_secret="",
    )
    test_app = _make_app()
    test_app.add_middleware(JWTAuthMiddleware, auth_settings=settings)
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=test_app), base_url="http://testserver"
    )

    token = _make_hs256_token({"sub": "x"})
    resp = await client.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
