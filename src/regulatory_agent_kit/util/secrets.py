"""Secrets manager integration — pluggable backends for credential retrieval.

Supports Vault, AWS Secrets Manager, GCP Secret Manager, and plain
environment variables.  All backends implement the ``SecretsBackend``
protocol.  Secret references can use URI schemes for routing:

- ``vault://secret/data/rak/llm-key``
- ``aws-sm://rak/prod/anthropic-key``
- ``gcp-sm://projects/123/secrets/anthropic-key/versions/latest``
- ``env://ANTHROPIC_API_KEY``  (explicit env var reference)
- Plain strings are returned as-is (literal values or env var content).
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Optional SDK imports
# ------------------------------------------------------------------

try:
    import boto3  # type: ignore[import-untyped]

    _HAS_BOTO3 = True
except ImportError:  # pragma: no cover
    _HAS_BOTO3 = False

try:
    from google.cloud import secretmanager as gcp_sm  # type: ignore[import-untyped]

    _HAS_GCP_SM = True
except ImportError:
    _HAS_GCP_SM = False

try:
    import hvac  # type: ignore[import-untyped]

    _HAS_HVAC = True
except ImportError:
    _HAS_HVAC = False


# ------------------------------------------------------------------
# Protocol
# ------------------------------------------------------------------


@runtime_checkable
class SecretsBackend(Protocol):
    """Pluggable interface for retrieving secrets by key."""

    def get_secret(self, key: str) -> str:
        """Return the secret value for *key*.

        Raises:
            KeyError: When the secret does not exist.
        """
        ...  # pragma: no cover


# ------------------------------------------------------------------
# Environment variable backend (default / development)
# ------------------------------------------------------------------


class EnvVarSecretsBackend:
    """Reads secrets from environment variables.

    This is the default backend used in development and Lite Mode.
    """

    def get_secret(self, key: str) -> str:
        """Return the value of environment variable *key*.

        Raises:
            KeyError: When the variable is not set.
        """
        value = os.environ.get(key)
        if value is None:
            msg = f"Environment variable not set: {key}"
            raise KeyError(msg)
        return value


# ------------------------------------------------------------------
# AWS Secrets Manager backend
# ------------------------------------------------------------------


class AWSSecretsManagerBackend:
    """Retrieves secrets from AWS Secrets Manager.

    Requires the ``boto3`` package.  Authentication uses the standard
    AWS credential chain (env vars, ~/.aws/credentials, IAM role).

    Args:
        region_name: AWS region for the Secrets Manager client.
    """

    def __init__(self, region_name: str = "us-east-1") -> None:
        if not _HAS_BOTO3:
            msg = "boto3 is required for AWSSecretsManagerBackend. Install with: pip install boto3"
            raise ImportError(msg)
        self._client: Any = boto3.client("secretsmanager", region_name=region_name)

    def get_secret(self, key: str) -> str:
        """Retrieve a secret value from AWS Secrets Manager.

        Args:
            key: The secret name or ARN.

        Raises:
            KeyError: When the secret does not exist or cannot be retrieved.
        """
        try:
            response = self._client.get_secret_value(SecretId=key)
            result: str = response["SecretString"]
            return result
        except Exception as exc:
            msg = f"Failed to retrieve secret '{key}' from AWS Secrets Manager: {exc}"
            raise KeyError(msg) from exc


# ------------------------------------------------------------------
# GCP Secret Manager backend
# ------------------------------------------------------------------


class GCPSecretManagerBackend:
    """Retrieves secrets from Google Cloud Secret Manager.

    Requires the ``google-cloud-secret-manager`` package.
    Authentication uses Application Default Credentials.

    Args:
        project_id: GCP project ID.  If ``None``, uses the default project.
    """

    def __init__(self, project_id: str | None = None) -> None:
        if not _HAS_GCP_SM:
            msg = (
                "google-cloud-secret-manager is required for GCPSecretManagerBackend. "
                "Install with: pip install google-cloud-secret-manager"
            )
            raise ImportError(msg)
        self._client: Any = gcp_sm.SecretManagerServiceClient()
        self._project_id = project_id

    def get_secret(self, key: str) -> str:
        """Retrieve a secret from GCP Secret Manager.

        Args:
            key: Full resource name (``projects/P/secrets/S/versions/V``)
                 or just the secret name (uses ``latest`` version and
                 configured project).

        Raises:
            KeyError: When the secret does not exist or cannot be retrieved.
        """
        try:
            if key.startswith("projects/"):
                name = key
            elif self._project_id:
                name = f"projects/{self._project_id}/secrets/{key}/versions/latest"
            else:
                msg = f"GCP project_id required to resolve short secret name: {key}"
                raise KeyError(msg)

            response = self._client.access_secret_version(request={"name": name})
            payload = response.payload
            result: str = payload.data.decode("utf-8")
            return result
        except KeyError:
            raise
        except Exception as exc:
            msg = f"Failed to retrieve secret '{key}' from GCP Secret Manager: {exc}"
            raise KeyError(msg) from exc


# ------------------------------------------------------------------
# HashiCorp Vault backend
# ------------------------------------------------------------------


class VaultSecretsBackend:
    """Retrieves secrets from HashiCorp Vault (KV v2).

    Requires the ``hvac`` package.

    Args:
        url: Vault server URL (e.g., ``https://vault.example.com:8200``).
        token: Vault authentication token.  If ``None``, reads from
               ``VAULT_TOKEN`` environment variable.
        mount_point: KV v2 mount point (default: ``secret``).
    """

    def __init__(
        self,
        url: str = "http://127.0.0.1:8200",
        token: str | None = None,
        mount_point: str = "secret",
    ) -> None:
        if not _HAS_HVAC:
            msg = "hvac is required for VaultSecretsBackend. Install with: pip install hvac"
            raise ImportError(msg)
        resolved_token = token or os.environ.get("VAULT_TOKEN", "")
        self._client: Any = hvac.Client(url=url, token=resolved_token)
        self._mount_point = mount_point

    def get_secret(self, key: str) -> str:
        """Retrieve a secret from Vault KV v2.

        Args:
            key: Path under the mount point (e.g., ``rak/llm-key``).
                 The first key in the ``data`` dict is returned.

        Raises:
            KeyError: When the secret does not exist or cannot be retrieved.
        """
        try:
            kv_engine = self._client.secrets.kv.v2
            response = kv_engine.read_secret_version(path=key, mount_point=self._mount_point)
            secret_data = response["data"]
            data: dict[str, Any] = secret_data["data"]
            if not data:
                msg = f"Secret at '{key}' exists but has no data"
                raise KeyError(msg)
            # Return the first value (convention: single-value secrets)
            return str(next(iter(data.values())))
        except KeyError:
            raise
        except Exception as exc:
            msg = f"Failed to retrieve secret '{key}' from Vault: {exc}"
            raise KeyError(msg) from exc


# ------------------------------------------------------------------
# Factory
# ------------------------------------------------------------------


SecretsFactory = Callable[..., SecretsBackend]
"""Callable that creates a SecretsBackend from keyword arguments."""

_SECRETS_REGISTRY: dict[str, SecretsFactory] = {}


def register_secrets_backend(name: str, factory: SecretsFactory) -> None:
    """Register a secrets backend factory by name (Strategy Pattern)."""
    _SECRETS_REGISTRY[name] = factory


# Built-in registrations
register_secrets_backend("env", lambda **_kw: EnvVarSecretsBackend())
register_secrets_backend(
    "aws",
    lambda **kw: AWSSecretsManagerBackend(region_name=kw.get("aws_region", "us-east-1")),
)
register_secrets_backend(
    "gcp",
    lambda **kw: GCPSecretManagerBackend(project_id=kw.get("gcp_project_id")),
)
register_secrets_backend(
    "vault",
    lambda **kw: VaultSecretsBackend(
        url=kw.get("vault_url", "http://127.0.0.1:8200"),
        token=kw.get("vault_token"),
        mount_point=kw.get("vault_mount_point", "secret"),
    ),
)


def create_secrets_backend(
    backend_type: str = "env",
    **kwargs: Any,
) -> SecretsBackend:
    """Create a secrets backend via the strategy registry.

    Args:
        backend_type: Registered backend name (``env``, ``aws``, ``gcp``, ``vault``).
        **kwargs: Backend-specific configuration passed to the factory.

    Returns:
        A configured ``SecretsBackend`` instance.

    Raises:
        ValueError: If *backend_type* is not registered.
        ImportError: If the required SDK is not installed.
    """
    factory = _SECRETS_REGISTRY.get(backend_type)
    if factory is None:
        registered = ", ".join(sorted(_SECRETS_REGISTRY))
        msg = f"Unknown secrets backend: {backend_type!r}. Registered: {registered}"
        raise ValueError(msg)
    return factory(**kwargs)


# ------------------------------------------------------------------
# URI-based secret resolution
# ------------------------------------------------------------------


def resolve_secret(
    value: str,
    backend: SecretsBackend | None = None,
) -> str:
    """Resolve a secret reference to its plaintext value.

    Supports URI schemes for routing to specific backends:

    - ``vault://path/to/secret`` — Vault KV v2
    - ``aws-sm://secret-name`` — AWS Secrets Manager
    - ``gcp-sm://projects/P/secrets/S/versions/V`` — GCP Secret Manager
    - ``env://VAR_NAME`` — environment variable
    - Plain strings — returned as-is

    When a URI scheme is used, a backend for that scheme is created
    on-the-fly.  When *backend* is provided, it is used for non-URI
    values that look like key references (no scheme).

    Args:
        value: The secret reference or literal value.
        backend: Optional pre-configured backend for unschemed lookups.

    Returns:
        The resolved secret string.
    """
    if value.startswith("vault://"):
        path = value.removeprefix("vault://")
        vault_backend = create_secrets_backend("vault")
        return vault_backend.get_secret(path)

    if value.startswith("aws-sm://"):
        key = value.removeprefix("aws-sm://")
        aws_backend = create_secrets_backend("aws")
        return aws_backend.get_secret(key)

    if value.startswith("gcp-sm://"):
        key = value.removeprefix("gcp-sm://")
        gcp_backend = create_secrets_backend("gcp")
        return gcp_backend.get_secret(key)

    if value.startswith("env://"):
        var_name = value.removeprefix("env://")
        return EnvVarSecretsBackend().get_secret(var_name)

    # If a backend is provided, try it for unschemed references
    if backend is not None:
        try:
            return backend.get_secret(value)
        except KeyError:
            pass

    # Return as literal
    return value
