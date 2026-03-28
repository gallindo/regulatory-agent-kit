"""Impact analysis models — output of the Analyzer agent."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ASTRegion(BaseModel):
    """A region in source code identified by line and column ranges."""

    start_line: int = Field(..., ge=1, description="Starting line number (1-based).")
    end_line: int = Field(..., ge=1, description="Ending line number (1-based).")
    start_col: int = Field(..., ge=0, description="Starting column offset (0-based).")
    end_col: int = Field(..., ge=0, description="Ending column offset (0-based).")
    node_type: str = Field(
        ..., min_length=1, description="AST node type (e.g., 'class_declaration')."
    )


class RuleMatch(BaseModel):
    """A single regulation rule that matched against a code region."""

    rule_id: str = Field(..., min_length=1, description="Plugin rule identifier.")
    description: str = Field(..., description="Human-readable rule description.")
    severity: Literal["critical", "high", "medium", "low"] = Field(
        ..., description="Rule severity level."
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score of the match.")
    condition_evaluated: str = Field(
        ..., description="The Condition DSL expression that was evaluated."
    )


class FileImpact(BaseModel):
    """Impact assessment for a single file."""

    file_path: str = Field(..., min_length=1, description="Path to the affected file.")
    matched_rules: list[RuleMatch] = Field(
        default_factory=list, description="Rules that matched in this file."
    )
    suggested_approach: str = Field(
        default="", description="Agent-suggested remediation approach."
    )
    affected_regions: list[ASTRegion] = Field(
        default_factory=list, description="AST regions affected by matched rules."
    )


class ConflictRecord(BaseModel):
    """A conflict between rules from different regulations affecting the same code region."""

    conflicting_rule_ids: list[str] = Field(
        ..., min_length=2, description="IDs of the conflicting rules."
    )
    affected_regions: list[ASTRegion] = Field(
        ..., min_length=1, description="Overlapping AST regions."
    )
    description: str = Field(..., description="Human-readable conflict description.")
    resolution: str | None = Field(default=None, description="Resolution strategy if determined.")


class ImpactMap(BaseModel):
    """Complete impact analysis result for a repository."""

    files: list[FileImpact] = Field(
        default_factory=list, description="Per-file impact assessments."
    )
    conflicts: list[ConflictRecord] = Field(
        default_factory=list, description="Cross-rule conflicts detected."
    )
    analysis_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Overall analysis confidence score."
    )
