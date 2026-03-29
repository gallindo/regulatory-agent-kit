"""Tests for secrets manager backends and resolution."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from regulatory_agent_kit.util.secrets import (
    AWSSecretsManagerBackend,
    EnvVarSecretsBackend,
    GCPSecretManagerBackend,
    SecretsBackend,
    VaultSecretsBackend,
    create_secrets_backend,
    resolve_secret,
)

# ------------------------------------------------------------------
# EnvVarSecretsBackend
# ------------------------------------------------------------------


class TestEnvVarSecretsBackend:
    def test_reads_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_SECRET_KEY", "secret-value")
        backend = EnvVarSecretsBackend()
        assert backend.get_secret("TEST_SECRET_KEY") == "secret-value"

    def test_raises_for_missing_var(self) -> None:
        backend = EnvVarSecretsBackend()
        with pytest.raises(KeyError, match="not set"):
            backend.get_secret("NONEXISTENT_VAR_XYZ_12345")

    def test_implements_protocol(self) -> None:
        backend = EnvVarSecretsBackend()
        assert isinstance(backend, SecretsBackend)


# ------------------------------------------------------------------
# AWSSecretsManagerBackend
# ------------------------------------------------------------------


class TestAWSSecretsManagerBackend:
    def test_get_secret_calls_boto3(self) -> None:
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            "SecretString": "my-api-key"
        }
        with patch("boto3.client", return_value=mock_client):
            backend = AWSSecretsManagerBackend(region_name="eu-west-1")
        result = backend.get_secret("rak/prod/anthropic-key")
        assert result == "my-api-key"
        mock_client.get_secret_value.assert_called_once_with(
            SecretId="rak/prod/anthropic-key"
        )

    def test_raises_keyerror_on_failure(self) -> None:
        mock_client = MagicMock()
        mock_client.get_secret_value.side_effect = Exception("not found")
        with patch("boto3.client", return_value=mock_client):
            backend = AWSSecretsManagerBackend()
        with pytest.raises(KeyError, match="Failed to retrieve"):
            backend.get_secret("missing-secret")

    def test_implements_protocol(self) -> None:
        mock_client = MagicMock()
        with patch("boto3.client", return_value=mock_client):
            backend = AWSSecretsManagerBackend()
        assert isinstance(backend, SecretsBackend)


# ------------------------------------------------------------------
# GCPSecretManagerBackend
# ------------------------------------------------------------------


class TestGCPSecretManagerBackend:
    def test_raises_if_sdk_not_installed(self) -> None:
        with (
            patch("regulatory_agent_kit.util.secrets._HAS_GCP_SM", False),
            pytest.raises(ImportError, match="google-cloud-secret-manager"),
        ):
            GCPSecretManagerBackend()

    def test_get_secret_with_full_resource_name(self) -> None:
        mock_response = MagicMock()
        mock_response.payload.data = b"gcp-secret-value"
        mock_gcp_client = MagicMock()
        mock_gcp_client.access_secret_version.return_value = mock_response

        with (
            patch("regulatory_agent_kit.util.secrets._HAS_GCP_SM", True),
            patch(
                "regulatory_agent_kit.util.secrets.gcp_sm", create=True
            ) as mock_mod,
        ):
            mock_mod.SecretManagerServiceClient.return_value = mock_gcp_client
            backend = GCPSecretManagerBackend(project_id="my-project")

        result = backend.get_secret("projects/my-project/secrets/api-key/versions/latest")
        assert result == "gcp-secret-value"

    def test_get_secret_with_short_name(self) -> None:
        mock_response = MagicMock()
        mock_response.payload.data = b"short-name-val"
        mock_gcp_client = MagicMock()
        mock_gcp_client.access_secret_version.return_value = mock_response

        with (
            patch("regulatory_agent_kit.util.secrets._HAS_GCP_SM", True),
            patch(
                "regulatory_agent_kit.util.secrets.gcp_sm", create=True
            ) as mock_mod,
        ):
            mock_mod.SecretManagerServiceClient.return_value = mock_gcp_client
            backend = GCPSecretManagerBackend(project_id="proj")

        result = backend.get_secret("my-secret")
        assert result == "short-name-val"
        mock_gcp_client.access_secret_version.assert_called_once_with(
            request={"name": "projects/proj/secrets/my-secret/versions/latest"}
        )

    def test_raises_without_project_for_short_name(self) -> None:
        mock_gcp_client = MagicMock()
        with (
            patch("regulatory_agent_kit.util.secrets._HAS_GCP_SM", True),
            patch(
                "regulatory_agent_kit.util.secrets.gcp_sm", create=True
            ) as mock_mod,
        ):
            mock_mod.SecretManagerServiceClient.return_value = mock_gcp_client
            backend = GCPSecretManagerBackend(project_id=None)

        with pytest.raises(KeyError, match="project_id required"):
            backend.get_secret("short-name")


# ------------------------------------------------------------------
# VaultSecretsBackend
# ------------------------------------------------------------------


class TestVaultSecretsBackend:
    def test_raises_if_hvac_not_installed(self) -> None:
        with (
            patch("regulatory_agent_kit.util.secrets._HAS_HVAC", False),
            pytest.raises(ImportError, match="hvac"),
        ):
            VaultSecretsBackend()

    def test_get_secret_reads_kv_v2(self) -> None:
        mock_hvac_client = MagicMock()
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"value": "vault-secret-123"}}
        }

        with (
            patch("regulatory_agent_kit.util.secrets._HAS_HVAC", True),
            patch(
                "regulatory_agent_kit.util.secrets.hvac", create=True
            ) as mock_mod,
        ):
            mock_mod.Client.return_value = mock_hvac_client
            backend = VaultSecretsBackend(
                url="http://vault:8200",
                token="test-token",  # noqa: S106
                mount_point="secret",
            )

        result = backend.get_secret("rak/llm-key")
        assert result == "vault-secret-123"
        mock_hvac_client.secrets.kv.v2.read_secret_version.assert_called_once_with(
            path="rak/llm-key", mount_point="secret"
        )

    def test_raises_for_empty_data(self) -> None:
        mock_hvac_client = MagicMock()
        mock_hvac_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {}}
        }

        with (
            patch("regulatory_agent_kit.util.secrets._HAS_HVAC", True),
            patch(
                "regulatory_agent_kit.util.secrets.hvac", create=True
            ) as mock_mod,
        ):
            mock_mod.Client.return_value = mock_hvac_client
            backend = VaultSecretsBackend(token="t")  # noqa: S106

        with pytest.raises(KeyError, match="no data"):
            backend.get_secret("rak/empty")


# ------------------------------------------------------------------
# create_secrets_backend factory
# ------------------------------------------------------------------


class TestCreateSecretsBackend:
    def test_env_backend(self) -> None:
        backend = create_secrets_backend("env")
        assert isinstance(backend, EnvVarSecretsBackend)

    def test_aws_backend(self) -> None:
        mock_client = MagicMock()
        with patch("boto3.client", return_value=mock_client):
            backend = create_secrets_backend("aws", aws_region="eu-west-1")
        assert isinstance(backend, AWSSecretsManagerBackend)

    def test_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown secrets backend"):
            create_secrets_backend("unknown")


# ------------------------------------------------------------------
# resolve_secret
# ------------------------------------------------------------------


class TestResolveSecret:
    def test_env_uri(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_KEY", "resolved")
        assert resolve_secret("env://MY_KEY") == "resolved"

    def test_env_uri_missing(self) -> None:
        with pytest.raises(KeyError):
            resolve_secret("env://NONEXISTENT_KEY_XYZ_99")

    def test_aws_uri(self) -> None:
        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {"SecretString": "from-aws"}
        with patch("boto3.client", return_value=mock_client):
            result = resolve_secret("aws-sm://rak/prod/key")
        assert result == "from-aws"

    def test_plain_value_returned_as_is(self) -> None:
        assert resolve_secret("literal-value") == "literal-value"

    def test_plain_value_with_backend_fallback(self) -> None:
        mock_backend = MagicMock(spec=SecretsBackend)
        mock_backend.get_secret.return_value = "from-backend"
        result = resolve_secret("my-key", backend=mock_backend)
        assert result == "from-backend"

    def test_plain_value_backend_miss_returns_literal(self) -> None:
        mock_backend = MagicMock(spec=SecretsBackend)
        mock_backend.get_secret.side_effect = KeyError("not found")
        result = resolve_secret("literal", backend=mock_backend)
        assert result == "literal"
