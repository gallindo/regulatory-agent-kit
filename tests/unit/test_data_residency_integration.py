"""Tests for data residency router integration in pipeline activities."""

from __future__ import annotations

from unittest.mock import patch

from regulatory_agent_kit.orchestration.activities import _resolve_model


class TestResolveModelWithJurisdiction:
    """Verify _resolve_model routes correctly based on jurisdiction and content."""

    def test_default_model_no_jurisdiction(self) -> None:
        """No jurisdiction returns the built-in default model."""
        with patch.dict("os.environ", {}, clear=True):
            model = _resolve_model()
            assert model == "litellm/anthropic/claude-sonnet-4-6"

    def test_env_override_ignores_jurisdiction(self) -> None:
        """RAK_LLM_MODEL env var takes precedence over jurisdiction routing."""
        with patch.dict("os.environ", {"RAK_LLM_MODEL": "custom/model"}):
            model = _resolve_model(jurisdiction="EU")
            assert model == "custom/model"

    def test_eu_jurisdiction_routes_to_eu_model(self) -> None:
        """EU jurisdiction routes to a Bedrock EU model."""
        with patch.dict("os.environ", {}, clear=True):
            model = _resolve_model(jurisdiction="EU")
            assert model == "bedrock/eu/claude-sonnet-4-6"

    def test_br_jurisdiction_routes_to_br_model(self) -> None:
        """BR jurisdiction routes to a Bedrock Brazil model."""
        with patch.dict("os.environ", {}, clear=True):
            model = _resolve_model(jurisdiction="BR")
            assert model == "bedrock/br/claude-sonnet-4-6"

    def test_us_jurisdiction_routes_to_us_model(self) -> None:
        """US jurisdiction routes to the Anthropic API model."""
        with patch.dict("os.environ", {}, clear=True):
            model = _resolve_model(jurisdiction="US")
            assert model == "anthropic/claude-sonnet-4-6"

    def test_unknown_jurisdiction_returns_default(self) -> None:
        """Unknown jurisdiction falls back to the default region model."""
        with patch.dict("os.environ", {}, clear=True):
            model = _resolve_model(jurisdiction="UNKNOWN_COUNTRY")
            assert model == "anthropic/claude-sonnet-4-6"

    def test_content_with_pii_uses_primary_tier(self) -> None:
        """PII in content forces primary tier for strict routing."""
        with patch.dict("os.environ", {}, clear=True):
            model = _resolve_model(
                jurisdiction="EU",
                content="Email: user@example.com, SSN: 123-45-6789",
            )
            # PII detected + EU jurisdiction -> primary tier bedrock/eu model
            assert model == "bedrock/eu/claude-sonnet-4-6"

    def test_content_without_pii(self) -> None:
        """Content without PII still routes by jurisdiction."""
        with patch.dict("os.environ", {}, clear=True):
            model = _resolve_model(
                jurisdiction="EU",
                content="No personal data here",
            )
            assert model == "bedrock/eu/claude-sonnet-4-6"

    def test_de_jurisdiction_maps_to_eu(self) -> None:
        """German jurisdiction maps to EU region, same model as EU."""
        with patch.dict("os.environ", {}, clear=True):
            model_de = _resolve_model(jurisdiction="DE")
            model_eu = _resolve_model(jurisdiction="EU")
            assert model_de == model_eu

    def test_empty_jurisdiction_returns_default(self) -> None:
        """Empty string jurisdiction returns the built-in default."""
        with patch.dict("os.environ", {}, clear=True):
            model = _resolve_model(jurisdiction="")
            assert model == "litellm/anthropic/claude-sonnet-4-6"

    def test_au_jurisdiction_routes_to_ap_model(self) -> None:
        """Australian jurisdiction routes to Asia-Pacific model."""
        with patch.dict("os.environ", {}, clear=True):
            model = _resolve_model(jurisdiction="AU")
            assert model == "bedrock/ap/claude-sonnet-4-6"

    def test_pii_with_default_region_no_escalation(self) -> None:
        """PII with a default-region jurisdiction does not escalate."""
        with patch.dict("os.environ", {}, clear=True):
            model = _resolve_model(
                jurisdiction="GLOBAL",
                content="Email: user@example.com",
            )
            # GLOBAL maps to "default" region; PII doesn't escalate for default
            assert model == "anthropic/claude-sonnet-4-6"

    def test_env_override_with_content(self) -> None:
        """RAK_LLM_MODEL env var takes precedence even with PII content."""
        with patch.dict("os.environ", {"RAK_LLM_MODEL": "override/model"}):
            model = _resolve_model(
                jurisdiction="EU",
                content="SSN: 123-45-6789",
            )
            assert model == "override/model"
