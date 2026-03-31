"""Tests for plugin certification tiers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path  # noqa: TC003

import pytest
from pydantic import ValidationError

from regulatory_agent_kit.plugins.certification import (
    certify_plugin,
    validate_for_certification,
)
from regulatory_agent_kit.plugins.schema import (
    Certification,
    RegulationPlugin,
    ReviewRecord,
)
from tests.helpers import minimal_plugin as _minimal_plugin


class TestCertificationModel:
    def test_default_tier(self) -> None:
        cert = Certification()
        assert cert.tier == "technically_valid"
        assert cert.reviews == []

    def test_technically_valid_no_reviews_needed(self) -> None:
        cert = Certification(tier="technically_valid")
        assert cert.tier == "technically_valid"

    def test_community_reviewed_requires_two_reviews(self) -> None:
        with pytest.raises(ValidationError, match="at least 2 reviews"):
            Certification(tier="community_reviewed", reviews=[])

    def test_community_reviewed_with_one_review_rejected(self) -> None:
        reviews = [
            ReviewRecord(
                reviewer="alice@example.com",
                reviewed_at=datetime.now(tz=UTC),
            ),
        ]
        with pytest.raises(ValidationError, match="at least 2 reviews"):
            Certification(tier="community_reviewed", reviews=reviews)

    def test_community_reviewed_with_two_reviews(self) -> None:
        reviews = [
            ReviewRecord(
                reviewer="alice@example.com",
                reviewed_at=datetime.now(tz=UTC),
            ),
            ReviewRecord(
                reviewer="bob@example.com",
                reviewed_at=datetime.now(tz=UTC),
            ),
        ]
        cert = Certification(tier="community_reviewed", reviews=reviews)
        assert cert.tier == "community_reviewed"
        assert len(cert.reviews) == 2

    def test_official_requires_certified_by(self) -> None:
        with pytest.raises(ValidationError, match="certified_by"):
            Certification(tier="official")

    def test_official_with_certified_by(self) -> None:
        cert = Certification(tier="official", certified_by="core-team@example.com")
        assert cert.tier == "official"

    def test_invalid_tier_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Certification(tier="bogus")  # type: ignore[arg-type]

    def test_ci_validated_default_false(self) -> None:
        cert = Certification()
        assert cert.ci_validated is False

    def test_certified_at_default_none(self) -> None:
        cert = Certification()
        assert cert.certified_at is None


class TestReviewRecord:
    def test_create_review(self) -> None:
        review = ReviewRecord(
            reviewer="alice@example.com",
            reviewed_at=datetime.now(tz=UTC),
            comments="Looks good",
        )
        assert review.reviewer == "alice@example.com"
        assert review.comments == "Looks good"

    def test_review_default_comments(self) -> None:
        review = ReviewRecord(
            reviewer="bob@example.com",
            reviewed_at=datetime.now(tz=UTC),
        )
        assert review.comments == ""

    def test_review_preserves_timestamp(self) -> None:
        ts = datetime(2025, 6, 15, 12, 0, 0, tzinfo=UTC)
        review = ReviewRecord(reviewer="alice@example.com", reviewed_at=ts)
        assert review.reviewed_at == ts


class TestRegulationPluginCertification:
    def test_plugin_has_default_certification(self) -> None:
        plugin = RegulationPlugin.model_validate(_minimal_plugin())
        assert plugin.certification.tier == "technically_valid"
        assert plugin.certification.ci_validated is False

    def test_plugin_with_explicit_certification(self) -> None:
        data = _minimal_plugin(
            certification={
                "tier": "official",
                "certified_by": "admin@example.com",
            }
        )
        plugin = RegulationPlugin.model_validate(data)
        assert plugin.certification.tier == "official"
        assert plugin.certification.certified_by == "admin@example.com"


class TestValidateForCertification:
    def test_valid_plugin(self, tmp_path: Path) -> None:
        plugin_file = tmp_path / "test-plugin.yaml"
        plugin_file.write_text(
            "id: test-reg\n"
            "name: Test Regulation\n"
            "version: '1.0'\n"
            "jurisdiction: EU\n"
            "authority: Test Authority\n"
            "effective_date: '2025-01-01'\n"
            "source_url: https://example.com/regulation\n"
            "disclaimer: This is not legal advice.\n"
            "rules:\n"
            "  - id: R1\n"
            "    description: Test rule\n"
            "    severity: medium\n"
            "    affects:\n"
            "      - pattern: '**/*.py'\n"
            "        condition: 'has_method(foo)'\n"
            "    remediation:\n"
            "      strategy: add_annotation\n"
            "      template: templates/fix.j2\n"
        )
        is_valid, errors = validate_for_certification(plugin_file)
        assert is_valid
        assert errors == []

    def test_invalid_plugin_file(self, tmp_path: Path) -> None:
        plugin_file = tmp_path / "bad.yaml"
        plugin_file.write_text("not: valid: yaml: {{")
        is_valid, errors = validate_for_certification(plugin_file)
        assert not is_valid
        assert len(errors) > 0

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        plugin_file = tmp_path / "does-not-exist.yaml"
        is_valid, errors = validate_for_certification(plugin_file)
        assert not is_valid
        assert len(errors) > 0


class TestCertifyPlugin:
    def test_certify_technically_valid(self) -> None:
        plugin = RegulationPlugin.model_validate(_minimal_plugin())
        cert = certify_plugin(plugin)
        assert cert.tier == "technically_valid"
        assert cert.ci_validated is True
        assert cert.certified_at is not None

    def test_certify_with_name(self) -> None:
        plugin = RegulationPlugin.model_validate(_minimal_plugin())
        cert = certify_plugin(plugin, tier="official", certified_by="admin@example.com")
        assert cert.tier == "official"
        assert cert.certified_by == "admin@example.com"

    def test_certify_sets_timestamp(self) -> None:
        plugin = RegulationPlugin.model_validate(_minimal_plugin())
        before = datetime.now(tz=UTC)
        cert = certify_plugin(plugin)
        after = datetime.now(tz=UTC)
        assert cert.certified_at is not None
        assert before <= cert.certified_at <= after

    def test_certify_non_technically_valid_not_ci_validated(self) -> None:
        plugin = RegulationPlugin.model_validate(_minimal_plugin())
        cert = certify_plugin(plugin, tier="official", certified_by="admin@example.com")
        assert cert.ci_validated is False
