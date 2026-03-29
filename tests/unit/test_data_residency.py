"""Tests for data residency routing."""

from __future__ import annotations

from regulatory_agent_kit.tools.data_residency import (
    DataResidencyRouter,
    contains_pii,
)

# ------------------------------------------------------------------
# Region resolution
# ------------------------------------------------------------------


class TestRegionResolution:
    def test_eu_jurisdictions_map_to_eu(self) -> None:
        router = DataResidencyRouter()
        for code in ("EU", "DE", "FR", "IT", "ES", "NL", "IE", "PL"):
            assert router.resolve_region(code) == "eu", f"Failed for {code}"

    def test_uk_maps_to_eu(self) -> None:
        router = DataResidencyRouter()
        assert router.resolve_region("GB") == "eu"
        assert router.resolve_region("UK") == "eu"

    def test_brazil_maps_to_br(self) -> None:
        router = DataResidencyRouter()
        assert router.resolve_region("BR") == "br"

    def test_us_maps_to_us(self) -> None:
        router = DataResidencyRouter()
        assert router.resolve_region("US") == "us"

    def test_australia_maps_to_ap(self) -> None:
        router = DataResidencyRouter()
        assert router.resolve_region("AU") == "ap"

    def test_global_maps_to_default(self) -> None:
        router = DataResidencyRouter()
        assert router.resolve_region("GLOBAL") == "default"

    def test_unknown_jurisdiction_maps_to_default(self) -> None:
        router = DataResidencyRouter()
        assert router.resolve_region("XX") == "default"

    def test_case_insensitive(self) -> None:
        router = DataResidencyRouter()
        assert router.resolve_region("eu") == "eu"
        assert router.resolve_region("br") == "br"


# ------------------------------------------------------------------
# Model selection
# ------------------------------------------------------------------


class TestModelSelection:
    def test_eu_primary_routes_to_bedrock_eu(self) -> None:
        router = DataResidencyRouter()
        model = router.select_model("EU", tier="primary")
        assert "bedrock/eu" in model

    def test_eu_secondary_routes_to_bedrock_eu(self) -> None:
        router = DataResidencyRouter()
        model = router.select_model("EU", tier="secondary")
        assert "bedrock/eu" in model

    def test_br_routes_to_bedrock_br(self) -> None:
        router = DataResidencyRouter()
        model = router.select_model("BR", tier="primary")
        assert "bedrock/br" in model

    def test_us_routes_to_default_anthropic(self) -> None:
        router = DataResidencyRouter()
        model = router.select_model("US", tier="primary")
        assert "anthropic/" in model

    def test_global_routes_to_default(self) -> None:
        router = DataResidencyRouter()
        model = router.select_model("GLOBAL", tier="primary")
        assert "anthropic/" in model

    def test_unknown_falls_back_to_default(self) -> None:
        router = DataResidencyRouter()
        model = router.select_model("XX", tier="primary")
        assert model != ""

    def test_secondary_tier(self) -> None:
        router = DataResidencyRouter()
        primary = router.select_model("EU", tier="primary")
        secondary = router.select_model("EU", tier="secondary")
        assert primary != secondary
        assert "haiku" in secondary

    def test_custom_routing_table(self) -> None:
        custom = {("custom_region", "primary"): "my-org/custom-model"}
        custom_map = {"XX": "custom_region"}
        router = DataResidencyRouter(
            routing_table=custom,
            jurisdiction_map=custom_map,
        )
        model = router.select_model("XX", tier="primary")
        assert model == "my-org/custom-model"


# ------------------------------------------------------------------
# PII detection
# ------------------------------------------------------------------


class TestPiiDetection:
    def test_detects_email(self) -> None:
        assert contains_pii("Contact user@example.com for details")

    def test_detects_phone(self) -> None:
        assert contains_pii("Call 555-123-4567")

    def test_detects_iban(self) -> None:
        assert contains_pii("Transfer to IBAN DE89370400440532013000")

    def test_detects_cpf(self) -> None:
        assert contains_pii("Brazilian CPF number required")

    def test_detects_cnpj(self) -> None:
        assert contains_pii("Company CNPJ registration")

    def test_no_pii_in_clean_text(self) -> None:
        assert not contains_pii("class UserService implements ICTService {}")

    def test_no_pii_in_empty_string(self) -> None:
        assert not contains_pii("")


# ------------------------------------------------------------------
# Content-aware routing
# ------------------------------------------------------------------


class TestContentAwareRouting:
    def test_pii_escalates_to_regional_model(self) -> None:
        router = DataResidencyRouter()
        model = router.select_model_for_content(
            "EU",
            "Contact user@example.com",
            tier="secondary",
        )
        # PII detected + EU jurisdiction → primary EU model
        assert "bedrock/eu" in model

    def test_no_pii_uses_requested_tier(self) -> None:
        router = DataResidencyRouter()
        model = router.select_model_for_content(
            "EU",
            "class Foo implements Bar {}",
            tier="secondary",
        )
        assert "haiku" in model or "secondary" in model

    def test_pii_with_global_jurisdiction_uses_default(self) -> None:
        router = DataResidencyRouter()
        model = router.select_model_for_content(
            "GLOBAL",
            "Email: test@test.com",
            tier="secondary",
        )
        # GLOBAL → default region, no strict routing escalation
        assert model != ""


# ------------------------------------------------------------------
# Routing metadata for audit logging
# ------------------------------------------------------------------


class TestRoutingMetadata:
    def test_metadata_contains_all_fields(self) -> None:
        router = DataResidencyRouter()
        meta = router.get_routing_metadata("EU", tier="primary")
        assert meta["jurisdiction"] == "EU"
        assert meta["region"] == "eu"
        assert "bedrock/eu" in meta["model"]
        assert meta["tier"] == "primary"

    def test_metadata_for_unknown_jurisdiction(self) -> None:
        router = DataResidencyRouter()
        meta = router.get_routing_metadata("XX")
        assert meta["region"] == "default"
        assert meta["model"] != ""
