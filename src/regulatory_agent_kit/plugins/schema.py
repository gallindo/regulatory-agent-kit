"""Pydantic v2 models for regulation YAML plugins."""

from __future__ import annotations

from datetime import date, datetime  # noqa: TC003
from pathlib import Path  # noqa: TC003
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

CertificationTierLiteral = Literal[
    "technically_valid",
    "community_reviewed",
    "official",
]


class ReviewRecord(BaseModel):
    """Record of a domain expert review."""

    reviewer: str
    reviewed_at: datetime
    comments: str = ""


class Certification(BaseModel):
    """Plugin certification status."""

    tier: CertificationTierLiteral = "technically_valid"
    certified_at: datetime | None = None
    certified_by: str = ""
    reviews: list[ReviewRecord] = Field(default_factory=list)
    ci_validated: bool = False

    @model_validator(mode="after")
    def validate_tier_requirements(self) -> Certification:
        """Ensure tier requirements are met."""
        if self.tier == "community_reviewed" and len(self.reviews) < 2:
            msg = "community_reviewed tier requires at least 2 reviews"
            raise ValueError(msg)
        if self.tier == "official" and not self.certified_by:
            msg = "official tier requires certified_by to be set"
            raise ValueError(msg)
        return self


class AffectsClause(BaseModel):
    """A file-pattern + condition pair describing what code a rule targets."""

    pattern: str = Field(..., min_length=1, description="Glob pattern (e.g., '**/*.java').")
    condition: str = Field(..., min_length=1, description="Condition DSL expression.")


class Remediation(BaseModel):
    """How to fix a violation detected by a rule."""

    strategy: Literal[
        "add_annotation",
        "add_configuration",
        "replace_pattern",
        "add_dependency",
        "generate_file",
        "custom_agent",
    ] = Field(..., description="Remediation strategy type.")
    template: str = Field(..., min_length=1, description="Path to Jinja2 remediation template.")
    test_template: str | None = Field(default=None, description="Path to Jinja2 test template.")
    confidence_threshold: float = Field(
        default=0.85, ge=0.0, le=1.0, description="Minimum confidence to auto-apply."
    )


class Rule(BaseModel):
    """A single regulation rule within a plugin."""

    model_config = ConfigDict(extra="allow")

    id: str = Field(..., min_length=1, description="Unique rule identifier.")
    description: str = Field(..., min_length=1, description="Human-readable rule description.")
    severity: Literal["critical", "high", "medium", "low"] = Field(
        ..., description="Rule severity level."
    )
    affects: list[AffectsClause] = Field(
        ..., min_length=1, description="Code patterns this rule targets."
    )
    remediation: Remediation = Field(..., description="How to fix violations.")

    def get_template_paths(self, base_dir: Path) -> tuple[Path, Path | None]:
        """Return resolved (remediation_template, test_template) paths."""
        test_path = (
            base_dir / self.remediation.test_template if self.remediation.test_template else None
        )
        return base_dir / self.remediation.template, test_path


class CrossReference(BaseModel):
    """A cross-reference to another regulation."""

    regulation_id: str = Field(..., min_length=1, description="Referenced regulation plugin ID.")
    relationship: Literal[
        "does_not_override",
        "takes_precedence",
        "complementary",
        "supersedes",
        "references",
    ] = Field(..., description="Relationship type.")
    articles: list[str] = Field(default_factory=list, description="Referenced articles.")
    conflict_handling: (
        Literal[
            "escalate_to_human",
            "apply_both",
            "defer_to_referenced",
        ]
        | None
    ) = Field(default=None, description="How to handle conflicts.")


class RTS(BaseModel):
    """A Regulatory Technical Standard referenced by a regulation."""

    id: str = Field(..., min_length=1, description="RTS identifier.")
    name: str = Field(..., min_length=1, description="RTS name.")
    url: HttpUrl = Field(..., description="URL to the RTS document.")


class EventTrigger(BaseModel):
    """Describes the event that triggers this regulation's pipeline."""

    topic: str = Field(..., min_length=1, description="Event topic / message type.")
    schema_def: dict[str, str] = Field(
        default_factory=dict,
        alias="schema",
        description="Expected payload schema.",
    )


class RegulationPlugin(BaseModel):
    """Top-level model for a regulation YAML plugin file.

    Uses ``extra="allow"`` so domain-specific fields (e.g., ``dora_pillar``)
    are preserved in ``model_extra``.
    """

    model_config = ConfigDict(extra="allow")

    id: str = Field(..., min_length=1, description="Unique plugin identifier.")
    name: str = Field(..., min_length=1, description="Human-readable regulation name.")
    version: str = Field(..., min_length=1, description="Plugin version (semver).")
    effective_date: date = Field(..., description="When the regulation takes effect.")
    jurisdiction: str = Field(..., min_length=1, description="Jurisdiction (e.g., 'EU').")
    authority: str = Field(..., min_length=1, description="Issuing authority.")
    source_url: HttpUrl = Field(..., description="URL to the official regulation text.")
    disclaimer: str = Field(..., min_length=1, description="Legal disclaimer.")
    rules: list[Rule] = Field(..., min_length=1, description="Regulation rules.")
    regulatory_technical_standards: list[RTS] | None = Field(
        default=None, description="Referenced RTS documents."
    )
    cross_references: list[CrossReference] | None = Field(
        default=None, description="Cross-references to other regulations."
    )
    supersedes: str | None = Field(
        default=None, description="Plugin ID this regulation supersedes."
    )
    changelog: str = Field(default="", description="Changelog for this plugin version.")
    event_trigger: EventTrigger | None = Field(
        default=None, description="Event trigger configuration."
    )
    certification: Certification = Field(default_factory=Certification)

    def get_precedence_refs(self) -> list[tuple[str, str]]:
        """Return (regulation_id, relationship) pairs for precedence relationships."""
        if not self.cross_references:
            return []
        return [
            (ref.regulation_id, ref.relationship)
            for ref in self.cross_references
            if ref.relationship in ("takes_precedence", "supersedes")
        ]

    @model_validator(mode="after")
    def _validate_disclaimer(self) -> RegulationPlugin:
        """Ensure disclaimer is meaningful (not just whitespace)."""
        if not self.disclaimer.strip():
            msg = "Disclaimer must contain non-whitespace text."
            raise ValueError(msg)
        return self
