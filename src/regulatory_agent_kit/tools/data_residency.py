"""Data residency routing — selects region-appropriate LLM models.

Routes LLM calls to models deployed in the correct geographic region
based on the jurisdiction of the data being processed, as required by
GDPR (EU), LGPD (Brazil), and other data protection regulations.

See architecture.md Section 6 and sad.md RC-1.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

T = TypeVar("T")

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Region definitions
# ---------------------------------------------------------------------------

# Maps jurisdiction codes (from plugin YAML) to canonical region names.
JURISDICTION_REGION_MAP: dict[str, str] = {
    # European Union — GDPR
    "EU": "eu",
    "DE": "eu",
    "FR": "eu",
    "IT": "eu",
    "ES": "eu",
    "NL": "eu",
    "BE": "eu",
    "AT": "eu",
    "PT": "eu",
    "IE": "eu",
    "FI": "eu",
    "SE": "eu",
    "DK": "eu",
    "PL": "eu",
    "CZ": "eu",
    "RO": "eu",
    "BG": "eu",
    "HR": "eu",
    "SK": "eu",
    "SI": "eu",
    "HU": "eu",
    "LT": "eu",
    "LV": "eu",
    "EE": "eu",
    "CY": "eu",
    "MT": "eu",
    "LU": "eu",
    "GR": "eu",
    "EL": "eu",
    # United Kingdom — UK GDPR
    "GB": "eu",
    "UK": "eu",
    # Brazil — LGPD
    "BR": "br",
    # United States
    "US": "us",
    # Australia — CDR / CPS 230
    "AU": "ap",
    # Global / no restriction
    "GLOBAL": "default",
    "EXAMPLE": "default",
}


# ---------------------------------------------------------------------------
# Model routing table
# ---------------------------------------------------------------------------

# Maps (region, tier) to a LiteLLM model identifier.
# Tier: "primary" for complex reasoning, "secondary" for cost-optimised tasks.
MODEL_ROUTING_TABLE: dict[tuple[str, str], str] = {
    # Default (no residency constraint)
    ("default", "primary"): "anthropic/claude-sonnet-4-6",
    ("default", "secondary"): "anthropic/claude-haiku-4-5",
    # EU — GDPR: use AWS Bedrock eu-west-1 or Azure OpenAI westeurope
    ("eu", "primary"): "bedrock/eu/claude-sonnet-4-6",
    ("eu", "secondary"): "bedrock/eu/claude-haiku-4-5",
    # Brazil — LGPD: use AWS Bedrock sa-east-1
    ("br", "primary"): "bedrock/br/claude-sonnet-4-6",
    ("br", "secondary"): "bedrock/br/claude-haiku-4-5",
    # US — no specific constraint, use default Anthropic API
    ("us", "primary"): "anthropic/claude-sonnet-4-6",
    ("us", "secondary"): "anthropic/claude-haiku-4-5",
    # Asia-Pacific
    ("ap", "primary"): "bedrock/ap/claude-sonnet-4-6",
    ("ap", "secondary"): "bedrock/ap/claude-haiku-4-5",
}


# ---------------------------------------------------------------------------
# Content classification patterns
# ---------------------------------------------------------------------------

# Regex patterns that indicate data requiring residency protection.
_PII_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),  # email
    re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),  # phone (US-style)
    re.compile(r"\b\d{3}[-]?\d{2}[-]?\d{4}\b"),  # SSN-like
    re.compile(r"\bIBAN\b", re.IGNORECASE),
    re.compile(r"\bCPF\b", re.IGNORECASE),  # Brazilian tax ID
    re.compile(r"\bCNPJ\b", re.IGNORECASE),  # Brazilian company ID
]


def contains_pii(text: str) -> bool:
    """Check if *text* contains patterns that suggest PII presence."""
    return any(pat.search(text) for pat in _PII_PATTERNS)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


@dataclass
class DataResidencyRouter:
    """Routes LLM calls to region-appropriate models.

    Determines the correct region from the plugin's jurisdiction,
    optionally scans content for PII indicators, and returns the
    model identifier that should be used for the call.

    Args:
        default_model: Fallback model when no routing rule matches.
        routing_table: Override the default model routing table.
        jurisdiction_map: Override the default jurisdiction-to-region map.
    """

    default_model: str = "anthropic/claude-sonnet-4-6"
    routing_table: dict[tuple[str, str], str] = field(
        default_factory=lambda: dict(MODEL_ROUTING_TABLE)
    )
    jurisdiction_map: dict[str, str] = field(
        default_factory=lambda: dict(JURISDICTION_REGION_MAP)
    )

    def resolve_region(self, jurisdiction: str) -> str:
        """Map a jurisdiction code to a canonical region.

        Args:
            jurisdiction: ISO 3166-1 alpha-2 code or ``GLOBAL``.

        Returns:
            Region string (``eu``, ``us``, ``br``, ``ap``, ``default``).
        """
        return self.jurisdiction_map.get(jurisdiction.upper(), "default")

    def select_model(
        self,
        jurisdiction: str,
        tier: str = "primary",
    ) -> str:
        """Select the region-appropriate model for a jurisdiction.

        Args:
            jurisdiction: Plugin jurisdiction code.
            tier: ``primary`` for complex tasks, ``secondary`` for simple.

        Returns:
            LiteLLM model identifier.
        """
        region = self.resolve_region(jurisdiction)
        model = self.routing_table.get((region, tier))
        if model is None:
            model = self.routing_table.get(("default", tier), self.default_model)
            logger.debug(
                "No routing rule for region=%s tier=%s, using default: %s",
                region, tier, model,
            )
        else:
            logger.debug(
                "Routed jurisdiction=%s → region=%s → model=%s",
                jurisdiction, region, model,
            )
        return model

    def select_model_for_content(
        self,
        jurisdiction: str,
        content: str,
        tier: str = "primary",
    ) -> str:
        """Select a model, escalating to strict routing if PII is detected.

        If the content contains PII patterns and the jurisdiction has a
        specific regional model, that model is always used regardless of
        the tier preference.

        Args:
            jurisdiction: Plugin jurisdiction code.
            content: The text content being sent to the LLM.
            tier: Preferred tier.

        Returns:
            LiteLLM model identifier.
        """
        if contains_pii(content):
            region = self.resolve_region(jurisdiction)
            if region != "default":
                logger.info(
                    "PII detected — enforcing strict region routing: %s",
                    region,
                )
                return self.select_model(jurisdiction, "primary")
        return self.select_model(jurisdiction, tier)

    def get_fallback_chain(self, jurisdiction: str) -> list[str]:
        """Return ordered list of models to try for a jurisdiction.

        Returns primary model first, then secondary for same region,
        then default primary, then default secondary.

        Args:
            jurisdiction: ISO 3166-1 alpha-2 code or ``GLOBAL``.

        Returns:
            Ordered list of model identifiers with no duplicates.
        """
        region = self.resolve_region(jurisdiction)
        chain: list[str] = []
        seen: set[str] = set()

        for r, tier in [
            (region, "primary"),
            (region, "secondary"),
            ("default", "primary"),
            ("default", "secondary"),
        ]:
            model = self.routing_table.get((r, tier))
            if model and model not in seen:
                chain.append(model)
                seen.add(model)

        return chain

    async def call_with_fallback(
        self,
        jurisdiction: str,
        call_fn: Callable[[str], Awaitable[T]],
    ) -> T:
        """Execute a call with automatic fallback through the model chain.

        Tries each model in the fallback chain in order. If a model fails,
        logs a warning and moves to the next model. If all models fail,
        raises ``RuntimeError`` with details of each failure.

        Args:
            jurisdiction: Jurisdiction code for routing.
            call_fn: Async callable that takes a model name and returns a result.
                     Raises an exception on failure.

        Returns:
            Result from the first successful call.

        Raises:
            RuntimeError: If all models in the fallback chain fail.
        """
        chain = self.get_fallback_chain(jurisdiction)
        errors: list[tuple[str, Exception]] = []

        for model in chain:
            try:
                return await call_fn(model)
            except Exception as exc:
                logger.warning(
                    "Model %s failed for jurisdiction %s: %s",
                    model,
                    jurisdiction,
                    exc,
                )
                errors.append((model, exc))

        error_details = "; ".join(f"{m}: {e}" for m, e in errors)
        msg = f"All models failed for jurisdiction {jurisdiction}: {error_details}"
        raise RuntimeError(msg)

    def get_routing_metadata(self, jurisdiction: str, tier: str = "primary") -> dict[str, Any]:
        """Return routing decision metadata for audit logging.

        Returns:
            Dict with region, model, jurisdiction, and tier.
        """
        region = self.resolve_region(jurisdiction)
        model = self.select_model(jurisdiction, tier)
        return {
            "jurisdiction": jurisdiction,
            "region": region,
            "model": model,
            "tier": tier,
        }
