"""Tests for fallback model routing."""

from __future__ import annotations

import pytest

from regulatory_agent_kit.tools.data_residency import DataResidencyRouter


class TestGetFallbackChain:
    def setup_method(self) -> None:
        self.router = DataResidencyRouter()

    def test_eu_fallback_chain(self) -> None:
        chain = self.router.get_fallback_chain("DE")
        assert len(chain) >= 2
        assert chain[0] == "bedrock/eu/claude-sonnet-4-6"
        assert chain[1] == "bedrock/eu/claude-haiku-4-5"
        # Default models should be in chain too if different
        assert "anthropic/claude-sonnet-4-6" in chain

    def test_us_fallback_chain(self) -> None:
        chain = self.router.get_fallback_chain("US")
        assert chain[0] == "anthropic/claude-sonnet-4-6"
        assert chain[1] == "anthropic/claude-haiku-4-5"

    def test_default_fallback_chain(self) -> None:
        chain = self.router.get_fallback_chain("GLOBAL")
        assert chain[0] == "anthropic/claude-sonnet-4-6"
        assert chain[1] == "anthropic/claude-haiku-4-5"

    def test_no_duplicates_in_chain(self) -> None:
        chain = self.router.get_fallback_chain("US")
        assert len(chain) == len(set(chain))

    def test_chain_always_has_entries(self) -> None:
        chain = self.router.get_fallback_chain("UNKNOWN_JURISDICTION")
        assert len(chain) >= 1

    def test_br_fallback_chain(self) -> None:
        chain = self.router.get_fallback_chain("BR")
        assert chain[0] == "bedrock/br/claude-sonnet-4-6"

    def test_ap_fallback_chain(self) -> None:
        chain = self.router.get_fallback_chain("AU")
        assert chain[0] == "bedrock/ap/claude-sonnet-4-6"
        assert chain[1] == "bedrock/ap/claude-haiku-4-5"

    def test_us_chain_deduplicates_default(self) -> None:
        """US models are the same as default, so chain should not repeat them."""
        chain = self.router.get_fallback_chain("US")
        assert len(chain) == 2


class TestCallWithFallback:
    def setup_method(self) -> None:
        self.router = DataResidencyRouter()

    async def test_success_on_first_try(self) -> None:
        async def call_fn(model: str) -> str:
            return f"result-from-{model}"

        result = await self.router.call_with_fallback("US", call_fn)
        assert result.startswith("result-from-")

    async def test_fallback_on_primary_failure(self) -> None:
        call_count = 0

        async def call_fn(model: str) -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Primary down")
            return f"result-from-{model}"

        result = await self.router.call_with_fallback("EU", call_fn)
        assert call_count == 2
        assert result.startswith("result-from-")

    async def test_all_models_fail(self) -> None:
        async def call_fn(model: str) -> str:
            raise ConnectionError(f"{model} down")

        with pytest.raises(RuntimeError, match="All models failed"):
            await self.router.call_with_fallback("US", call_fn)

    async def test_fallback_preserves_return_type(self) -> None:
        async def call_fn(model: str) -> dict[str, str]:
            if "haiku" not in model:
                raise ValueError("Only haiku works")
            return {"model": model, "status": "ok"}

        result = await self.router.call_with_fallback("US", call_fn)
        assert result["status"] == "ok"
        assert "haiku" in result["model"]

    async def test_error_details_include_all_failures(self) -> None:
        async def call_fn(model: str) -> str:
            raise ConnectionError(f"{model} down")

        with pytest.raises(RuntimeError) as exc_info:
            await self.router.call_with_fallback("EU", call_fn)

        error_msg = str(exc_info.value)
        # Should mention all models that were tried
        assert "bedrock/eu/claude-sonnet-4-6" in error_msg
        assert "bedrock/eu/claude-haiku-4-5" in error_msg

    async def test_fallback_skips_to_third_model(self) -> None:
        call_count = 0

        async def call_fn(model: str) -> str:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ConnectionError(f"Model {call_count} down")
            return f"result-from-{model}"

        result = await self.router.call_with_fallback("EU", call_fn)
        assert call_count == 3
        assert result.startswith("result-from-")
